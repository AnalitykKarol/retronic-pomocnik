"""Robienie run (domyślnie Ultimate Healing, "adura vita"; parametry: ustaw()/CZARY) z blank runy trzymanej w ręce, zamiast tarczy.

Moduł nie rusza myszy ani klawiatury sam: cała reakcja ze światem idzie przez obiekt "środowisko"
(wstrzykiwany; w grze SrodowiskoGry, w testach atrapa). Czysta logika + stan z pamięci gry.

Sekwencja (stan wyprowadzany za każdym razem z pamięci ekwipunku i kontenerów, więc każdy krok
jest idempotentny i weryfikowany, a przerwanie w dowolnym miejscu kończy się powrotem tarczy):
  1. tarcza ze slotu ręki -> pierwsze wolne pole plecaka
  2. blank runa z plecaka -> slot ręki
  3. rzut czaru (klawisz UH_KLAWISZ), weryfikacja: slot zmienił zawartość, mana spadła
  4. powstała runa ze slotu -> pierwsze wolne pole plecaka (NIE jest używana)
  5. tarcza z plecaka -> slot ręki, weryfikacja z ekwipunku

Środowisko (duck typing), wszystkie metody mogą rzucać wyjątek (traktowany jak zerwane połączenie):
  zegar() -> float           spij(s)
  ekwipunek() -> {slot: {"id","ilosc"}} albo None      (kontenery.ekwipunek)
  kontenery() -> [kontener] albo None                  (kontenery.kontenery)
  mana() -> int albo None
  geometria() -> {"reka": {5: (x, y), 6: (x, y)}, "plecak": [(x, y), ...]} albo None
  przeciagnij(x1, y1, x2, y2)      klawisz(nazwa)
  przerwanie() -> None albo powód (stwór w widoku, HP, ucieczka...)
  log(tekst)    alarm(tekst)
  stan: dict (opcjonalny, trwały) z kluczem "tarcza_id" ustawianym, gdy tarcza jest zdjęta
"""

import time

# --- stałe (pokrętła integrowane w cavebot.py) ---------------------------------
UH_AKTYWNY = 0               # 0 = wyłączone domyślnie
UH_CZAR = "adura vita"       # słowa czaru runowego (tylko log/telemetria; rzut idzie hotkeyem)
UH_RUNA = "Ultimate Healing Rune"
UH_KLAWISZ = "F5"            # hotkey czaru w kliencie (musi rzucać UH_CZAR)
UH_KOSZT = 100               # mana na jedną runę
UH_REZERWA = 25              # mana zostawiona na leczenie (exura)
UH_MANA_MIN = None           # None = UH_KOSZT + UH_REZERWA (liczone przy wywołaniu)
# Gotowe zestawy: uh.ustaw("adura gran") ustawia UH_CZAR/UH_RUNA/UH_KOSZT (klawisz zostaje).
# UH wymaga lvl 24 u NPC; Intense Healing Rune (adura gran) lvl 15.
CZARY = {
    "adura vita": ("Ultimate Healing Rune", 100),
    "adura gran": ("Intense Healing Rune", 60),
    "adura": ("Light Healing Rune", 40),
}
UH_MIN_HP = 90               # % HP gracza wymagane do rozpoczęcia
UH_ODSTEP_S = 20.0           # min. odstęp między próbami (także po porażce)
UH_SLOT = 5                  # slot ekwipunku Tibii z tarczą: 5 = prawa ręka, 6 = lewa (potwierdzone z id)
KROK_RZEDU = 37                # px: odstęp rzędów slotów w oknie plecaka
UH_BLANK_ID = 3147           # blank rune (ID klienta Retronic, zaobserwowane w plecaku)
UH_MAKS_CZAS_S = 40.0        # budżet całej procedury (potem tylko powrót tarczy)
UH_CZAS_POWROTU_S = 25.0     # dodatkowy czas wyłącznie na przywrócenie tarczy
UH_MAKS_PROB = 2             # prób rzutu i prób każdego przeciągnięcia
UH_POTWIERDZ_S = 1.6         # czas na potwierdzenie przeciągnięcia w pamięci
UH_CAST_S = 2.2              # czas na potwierdzenie rzutu
UH_MAKS_AKCJI = 14           # twardy limit obiegów maszyny stanów
UH_PONOW_BRAK_MIEJSCA_S = 60.0   # s do kolejnej próby, gdy nie ma gdzie odłożyć tarczy (zamiast serii porażek)
UH_SPADEK_MANY = 0.5         # spadek many >= UH_KOSZT * tyle uznajemy za rzut

# Środki slotów ręki względem prostokąta panelu: wyznaczane z zrzutu (geometria_z_obrazu), nie stałe.
BOK_SLOTU = 34              # slot razem z ramką (jak loot.BOK_SLOTU)
ODSTEP_KOLUMN = 73           # lewa kolumna -> prawa kolumna (x lewych krawędzi)
ODSTEP_WIERSZY = 36
KOLUMNA_SLOTU = {5: "prawa", 6: "lewa"}   # slot Tibii -> kolumna panelu (5 = id 3426 tarcza, 6 = id 3264 miecz)


def ustaw(czar, klawisz=None, koszt=None):
    """Ustawia czar runowy modułu (CZARY albo własny: podaj koszt). Zwraca (czar, runa, koszt, klawisz)."""
    global UH_CZAR, UH_RUNA, UH_KOSZT, UH_KLAWISZ
    if czar in CZARY:
        UH_RUNA, UH_KOSZT = CZARY[czar]
    elif koszt is None:
        raise ValueError(f"nieznany czar {czar!r}: podaj koszt many")
    else:
        UH_RUNA = czar
    if koszt is not None:
        UH_KOSZT = int(koszt)
    UH_CZAR = czar
    if klawisz:
        UH_KLAWISZ = klawisz
    return UH_CZAR, UH_RUNA, UH_KOSZT, UH_KLAWISZ


_brak_miejsca_od = None      # zegar środowiska z ostatniej odmowy "brak miejsca na tarczę" (mozna_robic: pauza)


# --- decyzja: czy wolno zacząć ----------------------------------------------------
def mozna_robic(g, stwory, *, aktywny=None, min_hp=None, mana_min=None, ja=None, walka=False,
                ucieczka=False, loot=False, teraz=None, ostatnia=None, odstep=None, jedzenie=False):
    """(bool, powód). g: odpowiedź "gracz" (hp, max_hp, mana, max_mana; opcjonalnie "proc").
    stwory: lista z komendy "stwory" (może zawierać siebie: pomijany po nazwie `ja`).
    Dowolny obcy byt w widoku (stwór lub gracz) blokuje: runa trwa kilka sekund bez tarczy."""
    aktywny = UH_AKTYWNY if aktywny is None else aktywny
    min_hp = UH_MIN_HP if min_hp is None else min_hp
    if mana_min is None:
        mana_min = UH_MANA_MIN if UH_MANA_MIN is not None else UH_KOSZT + UH_REZERWA
    odstep = UH_ODSTEP_S if odstep is None else odstep
    if not aktywny:
        return False, "wyłączone"
    if walka:
        return False, "walka"
    if ucieczka:
        return False, "ucieczka"
    if loot:
        return False, "loot"
    if jedzenie:
        return False, "jedzenie"
    obce = [s for s in (stwory or [])
            if not (ja is not None and s.get("nazwa") == ja and s.get("gracz"))
            and s.get("hp", 100) > 0]
    if obce:
        return False, f"w widoku {len(obce)} (np. {obce[0].get('nazwa', '?')})"
    if g is None:
        return False, "brak odczytu gracza"
    hp, mx = g.get("hp"), g.get("max_hp")
    proc = g.get("proc")
    if proc is None and hp is not None and mx:
        proc = 100.0 * hp / mx
    if proc is None:
        return False, "brak HP"
    if proc < min_hp:
        return False, f"HP {proc:.0f}% < {min_hp}%"
    mana = g.get("mana")
    if mana is None:
        return False, "brak many"
    if mana < mana_min:
        return False, f"mana {mana} < {mana_min}"
    if ostatnia is not None and teraz is not None and teraz - ostatnia < odstep:
        return False, f"odstęp {teraz - ostatnia:.0f}s < {odstep:.0f}s"
    if teraz is not None and _brak_miejsca_od is not None and 0 <= teraz - _brak_miejsca_od < UH_PONOW_BRAK_MIEJSCA_S:
        return False, f"brak miejsca na tarczę, ponowię za {UH_PONOW_BRAK_MIEJSCA_S - (teraz - _brak_miejsca_od):.0f}s"
    return True, "ok"


# --- geometria slotów z zrzutu --------------------------------------------------
def geometria_z_obrazu(obraz, kontenery=None):
    """{"reka": {5: (x, y), 6: (x, y)}, "plecak": [(x, y)...], "runy": [(x, y)...]} albo None.
    "runy": siatka okna pojemnika na runy (Purple backpack, loot.czy_runy), pusta, gdy go nie ma na ekranie.
    kontenery (odczyt pamięci, opcjonalnie): role okien z dopasowania do pamięci (loot.dopasuj_okna);
    bez nich albo gdy dopasowanie nie wyjdzie: role z tytułów okien.
    Sloty ręki: dwa pola 34x34 w tym samym wierszu, 73 px od siebie, środkowy z trzech wierszy panelu
    ekwipunku (pary: szyja/plecak, ręce, pierścień/amunicja) pod polem głowy. Bez stałych pikseli:
    panel może leżeć gdziekolwiek w prawej kolumnie. Plecak: pierwsze okno roli "plecak" z loot.znajdz_okna."""
    import numpy as np
    import loot
    a = np.asarray(obraz.convert("RGB")).astype(np.int16)
    maska = loot._maska_ramki(a)
    szer = obraz.size[0]
    seg = {}
    for y in range(maska.shape[0]):
        if maska[y, szer // 2:].sum() < 20:
            continue
        for s, e in loot._przedzialy(maska[y]):
            if e - s == BOK_SLOTU and s >= szer // 2:
                seg.setdefault(y, set()).add(s)
    wiersze = []
    for y in sorted(seg):
        for x in seg[y]:
            if (x + ODSTEP_KOLUMN in seg[y] and x in seg.get(y + BOK_SLOTU - 1, ())
                    and x + ODSTEP_KOLUMN in seg.get(y + BOK_SLOTU - 1, ())):
                wiersze.append((y, x))
    if not wiersze:
        return None
    x0 = wiersze[0][1]
    gora = sorted({y for y, x in wiersze if x == x0})
    # panel ma trzy wiersze w kroku 36 px; środkowy to ręce
    for i in range(len(gora) - 2):
        if gora[i + 1] - gora[i] == ODSTEP_WIERSZY and gora[i + 2] - gora[i + 1] == ODSTEP_WIERSZY:
            y_reki = gora[i + 1]
            break
    else:
        return None
    # kontrola: pole głowy w środkowej kolumnie ~13 px nad pierwszym wierszem
    srodek_x = x0 + ODSTEP_KOLUMN // 2
    if not any(abs(srodek_x - s) <= 1 for yy in range(gora[i] - 15, gora[i] - 10) for s in seg.get(yy, ())):
        return None
    cy = y_reki + BOK_SLOTU // 2
    reka = {}
    for slot, kol in KOLUMNA_SLOTU.items():
        x = x0 + (ODSTEP_KOLUMN if kol == "prawa" else 0)
        reka[slot] = (x + BOK_SLOTU // 2, cy)
    plecak = []
    wszystkie = loot.znajdz_okna(obraz)
    if kontenery:
        try:
            przypisane, _ = loot.dopasuj_okna(obraz, wszystkie, kontenery)
        except Exception:
            przypisane = None
        if przypisane is not None:
            for o, k in zip(wszystkie, przypisane):
                o.rola = loot.rola_kontenera(k)
    okna_runy = [o for o in wszystkie if o.rola == "runy"]
    runy = _siatka_plecaka(maska, okna_runy[0]) if len(okna_runy) == 1 else []
    okna = [o for o in wszystkie if o.rola == "plecak"]
    if not okna:
        # tytuł okna bywa nierozpoznany (brak górnej ramki, np. gdy najechane pole pierwszego rzędu rozbiło
        # okno na kawałki): sklejamy kawałki bez tytułu i bierzemy najwyższe okno. Zgodność z pamięcią
        # (plecak, kolejność ikon) jest sprawdzana osobno: _plecak i weryfikuj_plecak przed każdym ruchem.
        bez = _sklej_okna([o for o in wszystkie if o.tytul is None and o.rola != "runy"])
        okna = bez[:1]
    if len(okna) == 1:
        plecak = _siatka_plecaka(maska, okna[0])
    elif len(okna) > 1:
        return {"reka": reka, "plecak": [], "runy": runy, "uwaga": "kilka okien plecaka"}
    return {"reka": reka, "plecak": plecak, "runy": runy}


def _sklej_okna(okna):
    """Kawałki tego samego okna (rozbitego przez niewykryte pola) w jedno: ta sama siatka kolumn i odstęp
    pionowy będący wielokrotnością kroku rzędu. Zwraca listę Okno od góry."""
    import loot
    krok = KROK_RZEDU
    wyn = []
    for o in sorted(okna, key=lambda o: min(s.y for s in o.sloty)):
        if wyn:
            poprz = wyn[-1]
            dol = max(s.y for s in poprz.sloty)
            gora = min(s.y for s in o.sloty)
            luka = (gora - dol) / krok
            wyrownane = all(min((s.x - t.x) % krok, (t.x - s.x) % krok) <= 1
                            for s in o.sloty[:1] for t in poprz.sloty[:1])
            if wyrownane and 1 <= round(luka) <= 3 and abs(luka - round(luka)) * krok <= 2:
                nowe = loot.Okno(poprz.gora, min(poprz.lewo, o.lewo), max(poprz.prawo, o.prawo),
                                 sorted(poprz.sloty + o.sloty, key=lambda s: (s.y, s.x)))
                nowe.tytul, nowe.rola = poprz.tytul, poprz.rola
                wyn[-1] = nowe
                continue
        wyn.append(o)
    return wyn


def _siatka_plecaka(maska, okno):
    """Środki wszystkich pól okna plecaka jako SIATKA (rząd po rzędzie), a nie lista wykrytych slotów.
    Wykrywanie slotów gubi pola: podświetlona (najechana myszą) ramka przestaje mieć kolor ramki, a ikony
    przerywają linie. Indeks z pamięci kontenera (slot k = rząd k // kol, kolumna k % kol) musi trafić w to
    samo pole, więc pozycje liczymy z kotwicy (lewy-górny róg pierwszego pola) i kroku 37 px, a liczbę rzędów
    i kolumn z linii ramek w masce (wystarczy 2 pola w rzędzie)."""
    sl = okno.sloty
    if not sl:
        return []
    krok = KROK_RZEDU
    x_lewy = min(s.x for s in sl)
    x_ramki = okno.lewo + 9                    # lewy slot leży 9 px od lewej ramki okna
    if x_lewy - 3 * krok <= x_ramki <= x_lewy - 30:
        x_lewy = x_ramki                       # cała lewa kolumna niewykryta
    y0 = min(s.y for s in sl)
    kol_maks = max(1, min(8, (okno.prawo - x_lewy) // krok))
    kol_maks = max(kol_maks, max(round((s.x - x_lewy) / krok) for s in sl) + 1)
    wys, szer = maska.shape

    def linia(y):
        if y < 0 or y >= wys:
            return False
        return int(maska[y, x_lewy:min(szer, x_lewy + kol_maks * krok)].sum()) >= BOK_SLOTU * 2

    while linia(y0 - krok):
        y0 -= krok
    rzedy = [y0]
    y_dol = max(s.y for s in sl)               # ostatni wykryty rząd: dolna ramka okna nie jest rzędem
    while len(rzedy) < 16 and rzedy[-1] + krok <= y_dol + 1 and linia(rzedy[-1] + krok):
        rzedy.append(rzedy[-1] + krok)
    kol = 0
    for k in range(kol_maks):
        x = x_lewy + k * krok
        if any(int(maska[y, x:x + BOK_SLOTU].sum()) >= BOK_SLOTU - 4 for y in rzedy if y < wys):
            kol = k + 1
    kol = max(kol, 1)
    return [(x_lewy + k * krok + BOK_SLOTU // 2, y + BOK_SLOTU // 2) for y in rzedy for k in range(kol)]


BLAD_TEN_SAM = 8.0            # maks. średni błąd (0-255) dwóch ikon tego samego przedmiotu (zmierzone: 0.0)
BLAD_INNY = 20.0              # min. średni błąd ikon różnych przedmiotów (zmierzone: >= 34)
BOK_IKONY = 24                # porównujemy środek pola (bez ramki i podświetlenia najechania)


def _ikona_pola(a, c):
    cx, cy = int(c[0]), int(c[1])
    h = BOK_IKONY // 2
    if cx - h < 0 or cy - h < 0 or cy + h > a.shape[0] or cx + h > a.shape[1]:
        return None
    return a[cy - h:cy + h, cx - h:cx + h]


def zgodnosc_plecaka(obraz, srodki, przedmioty):
    """(ok, powód): czy pola okna plecaka na zrzucie zgadzają się z kolejnością przedmiotów z pamięci.
    srodki: środki pól w kolejności indeksów kontenera (współrzędne zrzutu), przedmioty: lista
    {"slot", "id", "ilosc"}. Bez szablonów ikon: pole zajęte musi mieć ikonę, wolne ma być puste,
    a ikony przedmiotów o tym samym ID (pojedynczych) muszą być identyczne, o różnych ID różne.
    Wykrywa przesunięcie siatki o pole/wiersz, nieodświeżone okno i złe kolumny."""
    import numpy as np
    a = np.asarray(obraz.convert("RGB")).astype(np.int16)
    zajete = {p["slot"]: p for p in przedmioty}
    ikony = {}
    for i, c in enumerate(srodki):
        ik = _ikona_pola(a, c)
        if ik is None:
            return False, f"pole {i} poza zrzutem"
        g = ik.mean(axis=2)
        niepuste = int(((g <= 8) | (g >= 64)).sum()) >= 6
        if i in zajete and not niepuste:
            return False, f"pole {i}: pamięć ma przedmiot {zajete[i]['id']}, na ekranie pusto"
        if i not in zajete and niepuste:
            return False, f"pole {i}: pamięć ma pusto, na ekranie przedmiot"
        if i in zajete:
            ikony[i] = ik
    maska = np.ones((BOK_IKONY, BOK_IKONY), bool)
    maska[int(BOK_IKONY * 0.55):, int(BOK_IKONY * 0.42):] = False      # licznik stosu
    jedyne = [i for i, p in zajete.items() if i in ikony and p.get("ilosc", 1) == 1]
    for n, i in enumerate(jedyne):
        for j in jedyne[n + 1:]:
            blad = float(np.abs(ikony[i] - ikony[j]).sum(axis=2)[maska].mean() / 3)
            if zajete[i]["id"] == zajete[j]["id"] and blad > BLAD_TEN_SAM:
                return False, f"pola {i} i {j} to ten sam przedmiot {zajete[i]['id']}, a ikony różne ({blad:.0f})"
            if zajete[i]["id"] != zajete[j]["id"] and blad < BLAD_INNY:
                return False, (f"pola {i} ({zajete[i]['id']}) i {j} ({zajete[j]['id']}) to różne przedmioty, "
                               f"a ikony podobne ({blad:.0f})")
    return True, "ok"


# --- narzędzia stanu ----------------------------------------------------------------
class _Brak(Exception):
    pass


def _odczyt(env, proby=3, pauza=0.25):
    """(ekwipunek, kontenery) albo (None, None) po `proby` nieudanych odczytach."""
    for i in range(proby):
        try:
            e, k = env.ekwipunek(), env.kontenery()
        except Exception as ex:                   # zerwane połączenie z rdzeniem
            e, k = None, None
            env.log(f"[UH] odczyt: {type(ex).__name__}: {ex}")
        if e is not None and k:
            return e, k
        if i + 1 < proby:
            env.spij(pauza)
    return None, None


def _plecak(kontenery):
    """Jedyny kontener-plecak gracza (nazwa backpack/bag) albo None."""
    import loot
    pl = [k for k in kontenery if (k.get("nazwa") or "").casefold() in ("backpack", "bag")
          and not loot.czy_runy(k)]
    return pl[0] if len(pl) == 1 else None


def _runy(kontenery):
    """Jedyny pojemnik na runy (loot.czy_runy: Purple backpack) albo None."""
    import loot
    r = [k for k in kontenery or [] if loot.czy_runy(k)]
    return r[0] if len(r) == 1 else None


def _kont_dla(rodzaj, plecak, kontenery):
    return plecak if rodzaj == "plecak" else _runy(kontenery)


def _gdzie_blank(plecak, runy, tylko_pojedyncze=False, widoczne=None):
    """("plecak"|"runy", indeks pola) blank runy: najpierw główny plecak, potem pojemnik na runy.
    widoczne: {"plecak": ile pól widać w oknie, "runy": ...}; blank poza oknem (okno przycięte przez panel albo
    otwarte okno zwłok) ustępuje widocznemu, jeśli taki jest (13.10: blank na polu 13 przy 12 widocznych)."""
    for rodzaj, k in (("plecak", plecak), ("runy", runy)):
        if k is None:
            continue
        lim = (widoczne or {}).get(rodzaj)
        if lim is not None:
            c = [p["slot"] for p in k.get("przedmioty", [])
                 if p["id"] == UH_BLANK_ID and p["slot"] < lim
                 and (not tylko_pojedyncze or p.get("ilosc", 1) == 1)]
            if c:
                return rodzaj, c[-1]
        n = _gdzie(k, UH_BLANK_ID, tylko_pojedyncze)
        if n is not None:
            return rodzaj, n
    return None


def _wolne_runy(runy, geom):
    """Indeks pierwszego wolnego, WIDOCZNEGO pola pojemnika na runy (siatka jego okna) albo None."""
    if runy is None or not geom or not geom.get("runy"):
        return None
    n = _wolne(runy)
    return n if n is not None and n < len(geom["runy"]) else None


def _cel_tarczy_na_runach(runy, geom):
    """Pole (indeks) WIDOCZNEGO pola pojemnika na runy z samą runą, na które można upuścić tarczę, gdy żadne wolne
    pole nie jest widoczne (okno przycięte przez panel, a wolne pola leżą pod spodem). Serwer wstawia upuszczony
    przedmiot na początek kontenera (jak dla wolnego pola), o ile kontener nie jest pełny; pole z runą, nigdy
    z kontenerem, więc tarcza nie wpadnie do środka cudzego plecaka. None: brak takiego pola."""
    import loot
    if runy is None or not geom or not geom.get("runy"):
        return None
    if len(runy.get("przedmioty", [])) >= runy.get("pojemnosc", 0):
        return None
    wid = len(geom["runy"])
    c = [p["slot"] for p in runy.get("przedmioty", []) if p["slot"] < wid and p["id"] in loot.ID_RUN_W_POJEMNIKU]
    return c[-1] if c else None


def _cel_odkladu(plecak, runy, geom, runy_pierwsze, bez_runy=False):
    """("runy"|"plecak", pole) miejsca na odłożenie przedmiotu z ręki albo None.
    bez_runy: pojemnik na runy już odmówił (weryfikacja/przeciągnięcie) w tej procedurze: tylko plecak."""
    kol = (("runy", None if bez_runy else _wolne_runy(runy, geom)),
           ("plecak", _wolne(plecak) if plecak else None))
    # wolne pole plecaka poza widocznym oknem nie jest celem (okno przycięte przez panel)
    lim = len((geom or {}).get("plecak") or ())
    kol = tuple((r, None if r == "plecak" and n is not None and lim and n >= lim else n) for r, n in kol)
    if not runy_pierwsze:
        kol = kol[::-1]
    cel = next(((r, n) for r, n in kol if n is not None), None)
    if cel is None and not bez_runy:
        # brak widocznego wolnego pola (tarcza zajęła ostatnie): na pole z runą w pojemniku, jak tarcza
        n = _cel_tarczy_na_runach(runy, geom)
        if n is not None:
            cel = ("runy", n, "na_zajete")
    return cel


def _wolne(plecak):
    """Indeks pierwszego wolnego pola (kontener jest upakowany: sloty 0..n-1 zajęte) albo None."""
    n = len(plecak.get("przedmioty", []))
    return n if n < plecak.get("pojemnosc", 0) else None


def _gdzie(plecak, ident, tylko_pojedyncze=False):
    """Slot (indeks pola) przedmiotu o danym ID w plecaku albo None."""
    c = [p["slot"] for p in plecak.get("przedmioty", [])
         if p["id"] == ident and (not tylko_pojedyncze or p.get("ilosc", 1) == 1)]
    return c[-1] if c else None


class _Przebieg:
    def __init__(self, env, slot, klawisz=None, koszt=None):
        self.env, self.slot = env, slot
        self.klawisz = klawisz or UH_KLAWISZ
        self.koszt = UH_KOSZT if koszt is None else koszt
        self.kroki = []
        self.t0 = env.zegar()
        self.powod = None             # powód przerwania (None = idziemy do przodu)
        self.alarm = False
        self.tarcza_id = None
        self.rzucono = False          # runa powstała w ręce
        self.zdjeto = False
        self.proby = {}
        self.casty = 0
        self.bez_runy = False         # pojemnik na runy odmówił: dalej odkładamy tylko do plecaka

    def krok(self, nazwa, ok=True, **kw):
        self.kroki.append(dict(nazwa=nazwa, ok=ok, t=round(self.env.zegar() - self.t0, 2), **kw))
        self.env.log(f"[UH] {nazwa}" + (" OK" if ok else " BŁĄD") + (f" {kw}" if kw else ""))

    def czas(self):
        return self.env.zegar() - self.t0

    def przerwij(self, powod, alarm=False):
        if self.powod is None:
            self.powod = powod
        self.alarm = self.alarm or alarm
        self.krok("przerwanie", ok=False, powod=powod)


def _ekw_slot(ekw, slot):
    v = (ekw or {}).get(slot)
    if v is None:
        v = (ekw or {}).get(str(slot))
    return None if v is None else v.get("id")


def _czekaj(env, slot, warunek, ile_s, krok_s=0.15):
    """Odpytuje pamięć, aż warunek(ekw, kont) lub upłynie czas. Zwraca (spelniony, ekw, kont)."""
    t_koniec = env.zegar() + ile_s
    ekw = kont = None
    while True:
        try:
            ekw, kont = env.ekwipunek(), env.kontenery()
        except Exception:
            ekw, kont = None, None
        if ekw is not None and kont:
            try:
                if warunek(ekw, kont):
                    return True, ekw, kont
            except Exception:
                pass
        if env.zegar() >= t_koniec:
            return False, ekw, kont
        env.spij(krok_s)


def _przed_ruchem(p, z, do, geom, zrodlo_id, pojedyncze):
    """Powód odmowy przeciągnięcia (None = wolno). Sprawdza ŚWIEŻY stan: źródło ma mieć oczekiwane ID
    (w ręce albo w polu plecaka z pamięci), cel w plecaku ma być pierwszym wolnym polem, a okno plecaka
    na zrzucie ma zgadzać się z kolejnością z pamięci (środowisko: weryfikuj_plecak). Chwilową
    niezgodność (okno odświeża się z opóźnieniem) odpytujemy do UH_POTWIERDZ_S."""
    env = p.env
    weryf = getattr(env, "weryfikuj_plecak", None)
    powod = "brak odczytu"
    t_koniec = env.zegar() + UH_POTWIERDZ_S
    while True:
        powod = None
        try:
            ekw, kont = env.ekwipunek(), env.kontenery()
        except Exception as ex:
            ekw, kont = None, None
            powod = f"odczyt: {type(ex).__name__}"
        pl = _plecak(kont) if kont else None
        if powod is None and (ekw is None or pl is None):
            powod = "brak odczytu plecaka"
        if powod is None:
            przedm = pl.get("przedmioty", [])
            if "runy" in (z[0], do[0]) and _runy(kont) is None:
                powod = "brak pojemnika na runy w pamięci"
            if powod is None and z[0] == "reka":
                if zrodlo_id is not None and _ekw_slot(ekw, p.slot) != zrodlo_id:
                    powod = f"w ręce {_ekw_slot(ekw, p.slot)}, oczekiwano {zrodlo_id}"
            elif powod is None:
                kz = _kont_dla(z[0], pl, kont)
                w = next((x for x in kz.get("przedmioty", []) if x["slot"] == z[1]), None)
                if w is None:
                    powod = f"pole {z[1]} puste w pamięci"
                elif zrodlo_id is not None and w["id"] != zrodlo_id:
                    powod = f"pole {z[1]}: w pamięci {w['id']}, oczekiwano {zrodlo_id}"
                elif pojedyncze and w.get("ilosc", 1) != 1:
                    powod = f"pole {z[1]}: stos {w.get('ilosc')}"
            if powod is None and do[0] != "reka" and len(do) > 2:
                # upuszczenie na zajęte pole z runą (brak widocznego wolnego): kontener nie pełny, pole = runa
                import loot
                kd = _kont_dla(do[0], pl, kont)
                w = next((x for x in kd.get("przedmioty", []) if x["slot"] == do[1]), None)
                if len(kd.get("przedmioty", [])) >= kd.get("pojemnosc", 0):
                    powod = "kontener pełny"
                elif w is None or w["id"] not in loot.ID_RUN_W_POJEMNIKU:
                    powod = f"cel {do[1]} nie jest polem z runą"
            elif powod is None and do[0] != "reka":
                kd = _kont_dla(do[0], pl, kont)
                if do[1] != len(kd.get("przedmioty", [])) or do[1] >= kd.get("pojemnosc", 0):
                    powod = f"cel {do[1]} nie jest pierwszym wolnym polem ({len(kd.get('przedmioty', []))})"
            for rodzaj in ("plecak", "runy"):
                if powod is not None or not (z[0] == rodzaj or do[0] == rodzaj):
                    continue
                f = weryf if rodzaj == "plecak" else getattr(env, "weryfikuj_runy", None)
                if f is None:
                    if rodzaj == "runy" and weryf is not None:
                        powod = "brak weryfikacji okna pojemnika na runy"
                    continue
                try:
                    powod = f(geom, pl if rodzaj == "plecak" else _runy(kont))
                except Exception as ex:
                    if type(ex).__name__ == "ZrzutNiedostepny":
                        raise            # zrob_runa: powód "brak_zrzutu" (bez liczenia porażki UH)
                    powod = f"weryfikacja zrzutu: {type(ex).__name__}: {ex}"
        if powod is None:
            return None
        if env.zegar() >= t_koniec:
            return powod
        env.spij(0.15)


def _przeciagnij(p, z, do, geom, plecak, warunek, nazwa, zrodlo_id=None, pojedyncze=False, **kw):
    """Jedno przeciągnięcie z weryfikacją przed i po. z/do: ("reka",) albo ("plecak", indeks).
    zrodlo_id: ID, jakie MUSI być w źródle tuż przed ruchem (inaczej nie ruszamy niczego)."""
    def xy(w):
        if w[0] == "reka":
            return geom["reka"][p.slot]
        siatka = geom.get(w[0]) or []
        if w[1] >= len(siatka):
            raise _Brak(f"pole {w[0]} {w[1]} poza oknem ({len(siatka)})")
        return siatka[w[1]]
    try:
        (x1, y1), (x2, y2) = xy(z), xy(do)
    except _Brak as e:
        p.proby[nazwa] = p.proby.get(nazwa, 0) + 1
        p.krok(nazwa, ok=False, powod=str(e), **kw)
        return False
    odmowa = _przed_ruchem(p, z, do, geom, zrodlo_id, pojedyncze)
    if odmowa:
        p.proby[nazwa] = p.proby.get(nazwa, 0) + 1
        p.krok(nazwa, ok=False, powod=f"bez ruchu: {odmowa}", **kw)
        return False
    p.proby[nazwa] = p.proby.get(nazwa, 0) + 1
    try:
        p.env.przeciagnij(x1, y1, x2, y2)
    except Exception as ex:
        if type(ex).__name__ == "Zatrzymano":
            raise
        p.krok(nazwa, ok=False, powod=f"drag: {type(ex).__name__}: {ex}", **kw)
        return False
    ok, _, _ = _czekaj(p.env, p.slot, warunek, UH_POTWIERDZ_S)
    p.krok(nazwa, ok=ok, **kw)
    return ok


def _cast(p):
    """Jeden rzut + weryfikacja. Zwraca "ok" | "pusty" | "bez_efektu"."""
    env = p.env
    try:
        mana0 = env.mana()
    except Exception:
        mana0 = None
    p.casty += 1
    env.klawisz(p.klawisz)
    t_koniec = env.zegar() + UH_CAST_S
    ekw = None
    while True:
        try:
            ekw = env.ekwipunek()
        except Exception:
            ekw = None
        wid = _ekw_slot(ekw, p.slot) if ekw is not None else UH_BLANK_ID
        if ekw is not None and wid is None:
            p.krok("cast", ok=False, powod="slot pusty po rzuceniu", mana_przed=mana0)
            return "pusty"
        if ekw is not None and wid != UH_BLANK_ID:
            try:
                mana1 = env.mana()
            except Exception:
                mana1 = None
            spadek = None if mana0 is None or mana1 is None else mana0 - mana1
            if spadek is not None and spadek < p.koszt * UH_SPADEK_MANY:
                env.log(f"[UH] uwaga: runa powstała (id {wid}), ale mana spadła tylko o {spadek}")
            p.krok("cast", ok=True, id_runy=wid, spadek_many=spadek)
            return "ok"
        if env.zegar() >= t_koniec:
            try:
                mana1 = env.mana()
            except Exception:
                mana1 = None
            p.krok("cast", ok=False, powod="slot bez zmiany (czar się nie udał)",
                   mana_przed=mana0, mana_po=mana1)
            return "bez_efektu"
        env.spij(0.15)


def _wynik(p, wynik, powod=None):
    return {"wynik": wynik, "powod": powod, "kroki": p.kroki, "alarm": p.alarm,
            "czas_s": round(p.czas(), 2), "rzuty": p.casty}


def zrob_runa(env, slot=None, klawisz=None, koszt=None):
    """Cała procedura. Zwraca {"wynik": "ok"|"przerwane"|"brak_blank", "powod", "kroki", "alarm", ...}.
    "alarm": True = tarcza mogła zostać poza slotem (wymaga uwagi człowieka). Nie rzuca wyjątków poza STOP."""
    slot = UH_SLOT if slot is None else slot
    p = _Przebieg(env, slot, klawisz, koszt)
    try:
        return _przebieg(p)
    except Exception as ex:
        if type(ex).__name__ == "Zatrzymano":
            raise
        if type(ex).__name__ == "ZrzutNiedostepny":
            # 13.10: grim wisiał (okno niewidoczne/obciążenie): osobny powód, cavebot nie liczy porażki UH
            p.przerwij(f"brak_zrzutu: {ex}", alarm=p.zdjeto)
            return _wynik(p, "przerwane", p.powod)
        p.przerwij(f"wyjątek {type(ex).__name__}: {ex}", alarm=p.zdjeto)
        return _wynik(p, "przerwane", p.powod)


def _odmowa_miejsca(p):
    """Nie ma widocznego miejsca na tarczę: przerwanie bez alarmu i pauza UH_PONOW_BRAK_MIEJSCA_S w mozna_robic."""
    global _brak_miejsca_od
    _brak_miejsca_od = p.env.zegar()
    p.przerwij("brak_miejsca w plecaku na tarczę")


def _przebieg(p):
    env, slot = p.env, p.slot
    ekw, kont = _odczyt(env)
    if ekw is None:
        p.przerwij("brak_odczytu")
        return _wynik(p, "przerwane", p.powod)
    plecak = _plecak(kont)
    if plecak is None:
        p.przerwij("brak_plecaka (zero lub kilka okien plecaka)")
        return _wynik(p, "przerwane", p.powod)
    # powrót po poprzednim przerwaniu: tarcza zapamiętana jako zdjęta
    stan = getattr(env, "stan", None)
    zapamietana = stan.get("tarcza_id") if isinstance(stan, dict) else None
    if zapamietana and _ekw_slot(ekw, slot) != zapamietana:
        p.tarcza_id, p.zdjeto = zapamietana, True
        p.krok("wznowienie_powrotu", tarcza_id=zapamietana)
        p.powod = "wznowienie powrotu tarczy"
    else:
        wid = _ekw_slot(ekw, slot)
        if wid is None or wid == UH_BLANK_ID:
            p.przerwij("slot_bez_tarczy (pusty albo blank runa)")
            return _wynik(p, "przerwane", p.powod)
        p.tarcza_id = wid
    runy = _runy(kont)
    if not p.zdjeto:
        if _gdzie_blank(plecak, runy, tylko_pojedyncze=True) is None:
            if _gdzie_blank(plecak, runy) is not None:
                p.przerwij("blank_stos (ilosc > 1, przeciągnięcie otworzy okno ilości)")
                return _wynik(p, "przerwane", p.powod)
            p.krok("brak_blank", ok=False)
            return _wynik(p, "brak_blank", "w plecaku brak blank runy")
        if _wolne(plecak) is None and (runy is None or _wolne(runy) is None):
            _odmowa_miejsca(p)
            return _wynik(p, "przerwane", p.powod)
        powod = env.przerwanie()
        if powod:
            p.przerwij(f"przed startem: {powod}")
            return _wynik(p, "przerwane", p.powod)
    geom = env.geometria()
    if geom and geom.get("plecak"):
        geom = dict(geom, plecak=list(geom["plecak"])[:max(1, int(plecak.get("pojemnosc") or 0))])
    if not geom or slot not in geom.get("reka", {}) or not geom.get("plecak"):
        p.przerwij("brak_geometrii (nie widzę panelu ekwipunku albo okna plecaka)")
        return _wynik(p, "przerwane", p.powod)
    if geom.get("runy"):
        geom = dict(geom, runy=list(geom["runy"])[:max(1, int((runy or {}).get("pojemnosc") or 0))])

    termin = UH_MAKS_CZAS_S
    for _ in range(UH_MAKS_AKCJI):
        if p.powod is None and p.czas() > termin:
            p.przerwij("przekroczony czas procedury")
        if p.czas() > termin + UH_CZAS_POWROTU_S:
            p.przerwij("przekroczony czas powrotu tarczy", alarm=True)
            return _wynik(p, "przerwane", p.powod)
        ekw, kont = _odczyt(env)
        if ekw is None:
            p.przerwij("brak_odczytu w trakcie", alarm=p.zdjeto)
            return _wynik(p, "przerwane", p.powod)
        plecak = _plecak(kont)
        if plecak is None:
            p.przerwij("plecak zniknął z pamięci", alarm=p.zdjeto)
            return _wynik(p, "przerwane", p.powod)
        runy = _runy(kont)
        # środek procedury: stwór itp. => wracamy
        if p.powod is None and p.zdjeto:
            try:
                powod = env.przerwanie()
            except Exception as ex:
                powod = f"przerwanie: {type(ex).__name__}"
            if powod:
                p.przerwij(powod)
        wid = _ekw_slot(ekw, slot)
        wracaj = p.powod is not None or p.rzucono
        wolne = _wolne(plecak)

        if wid == p.tarcza_id:
            if p.zdjeto:
                p.zdjeto = False
                if isinstance(stan, dict):
                    stan.pop("tarcza_id", None)
                p.krok("tarcza_wrocila", ok=True, id=p.tarcza_id)
            if p.powod is not None or p.rzucono:
                break
            # krok 1: tarcza -> plecak
            if p.proby.get("tarcza_do_plecaka", 0) >= UH_MAKS_PROB:
                p.przerwij("tarcza nie schodzi ze slotu")
                break
            # 13.10: okno plecaka pokazuje tylko część pól (np. 8 z 20): wolne pole poza oknem = nie do trafienia;
            # wtedy tarcza idzie na widoczne wolne pole pojemnika na runy (stamtąd wraca do ręki)
            cel_t = None
            if wolne is not None and wolne < len(geom.get("plecak") or ()):
                cel_t = ("plecak", wolne)
            else:
                r_w = _wolne_runy(runy, geom)
                if r_w is not None:
                    cel_t = ("runy", r_w)
            if cel_t is None:
                r_z = _cel_tarczy_na_runach(runy, geom)
                if r_z is not None:
                    cel_t = ("runy", r_z, "na_zajete")
                    p.krok("tarcza_na_zajete_pole_runy", pole=r_z)
            if cel_t is None:
                _odmowa_miejsca(p)
                break
            if isinstance(stan, dict):
                stan["tarcza_id"] = p.tarcza_id      # zapis zamiaru przed ruchem (restart w środku)
            if _przeciagnij(p, ("reka",), cel_t, geom, plecak,
                         lambda e, k, s=slot, t=p.tarcza_id: _ekw_slot(e, s) != t,
                         "tarcza_do_plecaka", zrodlo_id=p.tarcza_id, id=p.tarcza_id, pole=cel_t[1], dokad=cel_t[0]):
                p.zdjeto = True
            continue

        if wid is None:
            if wracaj:
                n = _gdzie(plecak, p.tarcza_id)
                skad_t = "plecak"
                if n is None and runy is not None:
                    n, skad_t = _gdzie(runy, p.tarcza_id), "runy"
                if n is None:
                    p.przerwij("tarcza_zgubiona (brak w slocie i w plecaku)", alarm=True)
                    break
                if p.proby.get("tarcza_do_reki", 0) >= UH_MAKS_PROB:
                    p.przerwij("tarcza nie wróciła do slotu", alarm=True)
                    break
                _przeciagnij(p, (skad_t, n), ("reka",), geom, plecak,
                             lambda e, k, s=slot, t=p.tarcza_id: _ekw_slot(e, s) == t,
                             "tarcza_do_reki", zrodlo_id=p.tarcza_id, id=p.tarcza_id, pole=n, skad=skad_t)
                continue
            # slot pusty, tarcza w plecaku: blank do ręki
            zb = _gdzie_blank(plecak, runy, tylko_pojedyncze=True,
                              widoczne={"plecak": len(geom.get("plecak") or ()), "runy": len(geom.get("runy") or ())})
            if zb is None:
                p.przerwij("brak blank runy po zdjęciu tarczy")
                continue
            if zb[0] == "runy" and not (geom.get("runy") and zb[1] < len(geom["runy"])):
                p.przerwij("blank w pojemniku na runy poza oknem (brak geometrii)")
                continue
            if p.proby.get("blank_do_reki", 0) >= UH_MAKS_PROB:
                p.przerwij("blank runa nie trafia do slotu")
                continue
            _przeciagnij(p, zb, ("reka",), geom, plecak,
                         lambda e, k, s=slot: _ekw_slot(e, s) == UH_BLANK_ID,
                         "blank_do_reki", zrodlo_id=UH_BLANK_ID, pojedyncze=True, pole=zb[1], skad=zb[0])
            continue

        if wid == UH_BLANK_ID:
            if wracaj or p.casty >= UH_MAKS_PROB:
                if not wracaj:
                    p.przerwij("nieudany_cast (blank runa dalej w ręce po rzutach)")
                cel = _cel_odkladu(plecak, runy, geom, runy_pierwsze=False, bez_runy=p.bez_runy)
                if cel is None:
                    p.przerwij("brak_miejsca na blank rune", alarm=True)
                    break
                if p.proby.get("blank_do_plecaka", 0) >= UH_MAKS_PROB:
                    p.przerwij("blank runa nie wraca do plecaka", alarm=True)
                    break
                if not _przeciagnij(p, ("reka",), cel, geom, plecak,
                                    lambda e, k, s=slot: _ekw_slot(e, s) != UH_BLANK_ID,
                                    "blank_do_plecaka", zrodlo_id=UH_BLANK_ID, pole=cel[1], dokad=cel[0]) \
                        and cel[0] == "runy":
                    p.bez_runy = True
                continue
            res = _cast(p)
            if res == "ok":
                p.rzucono = True
            elif res == "pusty":
                p.przerwij("slot pusty po rzuceniu (czar się nie udał)")
            elif p.casty >= UH_MAKS_PROB:
                p.przerwij("nieudany_cast (mana nie spadła, slot bez zmiany)")
            continue

        # w slocie coś innego: powstała runa (albo cudzy przedmiot): do plecaka
        cel = _cel_odkladu(plecak, runy, geom, runy_pierwsze=True, bez_runy=p.bez_runy)
        if cel is None:
            p.przerwij("brak_miejsca na gotową runę", alarm=True)
            break
        if p.proby.get("runa_do_plecaka", 0) >= UH_MAKS_PROB:
            p.przerwij("runa nie schodzi ze slotu", alarm=True)
            break
        udane = _przeciagnij(p, ("reka",), cel, geom, plecak,
                             lambda e, k, s=slot: _ekw_slot(e, s) != wid,
                             "runa_do_plecaka", zrodlo_id=wid, id=wid, pole=cel[1], dokad=cel[0])
        if not udane and cel[0] == "runy":
            p.bez_runy = True
    else:
        p.przerwij("limit akcji", alarm=p.zdjeto)

    # końcowa weryfikacja z pamięci
    ekw, kont = _odczyt(env)
    wrocila = ekw is not None and _ekw_slot(ekw, slot) == p.tarcza_id
    if not wrocila:
        p.alarm = True
        if p.powod is None or "tarcza" not in p.powod:
            p.powod = (p.powod + "; " if p.powod else "") + "tarcza_nie_wrocila"
        p.krok("tarcza_nie_wrocila", ok=False)
        try:
            env.alarm("UH: tarcza poza slotem, sprawdź postać")
        except Exception:
            pass
        return _wynik(p, "przerwane", p.powod)
    if isinstance(stan, dict):
        stan.pop("tarcza_id", None)
    if p.powod is not None:
        return _wynik(p, "przerwane", p.powod)
    return _wynik(p, "ok")



def przywroc(env, slot=None, klawisz=None, koszt=None):
    """Awaryjny powrót tarczy (np. po restarcie bota z zapamiętanym stan["tarcza_id"]):
    wywołanie w spokoju przy starcie. Zwraca jak zrob_runa; bez zapamiętanej tarczy nic nie robi."""
    stan = getattr(env, "stan", None)
    if not (isinstance(stan, dict) and stan.get("tarcza_id")):
        return {"wynik": "ok", "powod": "nic do przywrócenia", "kroki": [], "alarm": False,
                "czas_s": 0.0, "rzuty": 0}
    return zrob_runa(env, slot, klawisz, koszt)


# --- warstwa wejścia/wyjścia (nie testowana na prawdziwym X11) -------------------------
class SrodowiskoGry:
    """Prawdziwe środowisko: gniazdo pomocnika, zrzut ekranu, mysz XTEST, klawisz hotkeya.
    postac: bot.Postac (klawisz), przerwanie: callable() -> None|powód (dostarcza cavebot)."""

    def __init__(self, postac, zapytaj, przerwanie, alarm=print, log=print, stan_plik=None):
        self.postac, self._zapytaj, self._przerwanie = postac, zapytaj, przerwanie
        self._alarm, self.log = alarm, log
        self.stan = {}

    def zegar(self):
        return time.monotonic()

    def spij(self, s):
        time.sleep(s)

    def ekwipunek(self):
        e = self._zapytaj({"cmd": "kontenery", "ekwipunek": True}).get("ekwipunek")
        return None if e is None else {int(k): v for k, v in e.items()}

    def kontenery(self):
        return self._zapytaj({"cmd": "kontenery"}).get("kontenery")

    def mana(self):
        return self._zapytaj({"cmd": "gracz"})["gracz"].get("mana")

    def geometria(self):
        import ekran
        obraz = ekran.zrzut()
        try:
            kontenery = self.kontenery()
        except Exception as ex:
            if type(ex).__name__ == "Zatrzymano":
                raise
            kontenery = None
        g = geometria_z_obrazu(obraz, kontenery)
        if not g:
            return None
        rozmiar = ekran._rozmiar_ekranu()
        plecak_obraz = list(g["plecak"])           # współrzędne zrzutu (do porównania ikon)
        runy_obraz = list(g.get("runy") or [])
        if obraz.size != rozmiar:                  # współrzędne zrzutu -> ekranu
            sx, sy = rozmiar[0] / obraz.size[0], rozmiar[1] / obraz.size[1]
            g = {"reka": {k: (round(x * sx), round(y * sy)) for k, (x, y) in g["reka"].items()},
                 "plecak": [(round(x * sx), round(y * sy)) for x, y in g["plecak"]],
                 "runy": [(round(x * sx), round(y * sy)) for x, y in runy_obraz]}
        g["plecak_obraz"] = plecak_obraz
        g["runy_obraz"] = runy_obraz
        return g

    def weryfikuj_runy(self, geom, kontener):
        """Jak weryfikuj_plecak, dla okna pojemnika na runy."""
        import ekran
        srodki = (geom.get("runy_obraz") or geom["runy"])[:len(geom["runy"])]
        ok, powod = zgodnosc_plecaka(ekran.zrzut(), srodki, kontener.get("przedmioty", []))
        return None if ok else f"ekran != pamięć (runy): {powod}"

    def weryfikuj_plecak(self, geom, kontener):
        """None, gdy pola okna plecaka na świeżym zrzucie zgadzają się z kolejnością z pamięci, inaczej powód."""
        import ekran
        srodki = (geom.get("plecak_obraz") or geom["plecak"])[:len(geom["plecak"])]
        ok, powod = zgodnosc_plecaka(ekran.zrzut(), srodki, kontener.get("przedmioty", []))
        return None if ok else f"ekran != pamięć: {powod}"

    def przeciagnij(self, x1, y1, x2, y2):
        import ekran
        with ekran.Mysz() as m:
            m.przeciagnij(x1, y1, x2, y2, drganie=2)

    def klawisz(self, nazwa):
        self.postac.klawisz(nazwa)

    def przerwanie(self):
        return self._przerwanie()

    def alarm(self, tekst):
        self._alarm(tekst)
