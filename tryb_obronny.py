"""Tryb obronny (25.10, zgon Geblish): zamiast ucieczki z progu HP bot BIJE tego, kto go bije, i leczy się w trakcie walki.

Pokrętło `TRYB_OBRONNY` (cavebot.py, 0 = wyłączony = zero zmian). Cała logika siedzi tutaj; cavebot.py ma tylko haki
(wołane wyłącznie przy TRYB_OBRONNY=1):
  inicjuj      - pola stanu w Cavebot.__init__
  ocen         - w tick() przy progu ucieczki: czy walczymy zamiast uciekać (wróg w <= OBRONA_WROG_ODL, HP w strefie walki,
                 nie ostateczność); zapis mobów/graczy z czaszką do bicia (`obrona_bij`: kandydaci() ich przepuszcza, także spoza
                 --potwory)
  blokada      - ucieczka już trwa, a kroki nie ruszają (mob obok): zamiast kręcić się w kółko bijemy blokującego
  lecz_tick    - leczenie w walce: (1) runa leczenia z plecaka na siebie, (2) brak runy = ROBIMY ją (blank + mana), (3) exura
                 (zwykły _zdrowie_czar_tick, odblokowany poniżej progu ucieczki), (4) ostatecznie ucieczka (ocen)
  pk_walka     - gracz z czaszką w zwarciu = walka zamiast ucieczki PK do depo
Pokrętła i opisy: stałe OBRONA_* i UH_LECZ_* w cavebot.py + pokretla.py.
"""
import sys

import bot


def _c(cb):
    """Moduł cavebot (stałe są pokrętłami nadpisywanymi przez pokretla.py w module, więc czytamy je z niego na bieżąco)."""
    for k in type(cb).__mro__:                       # mozg.py daje podklasę w __main__: szukamy modułu ze stałymi
        m = sys.modules.get(k.__module__)
        if m is not None and hasattr(m, "GRYZIE_OKNO"):
            return m
    return sys.modules["cavebot"]


def inicjuj(cb):
    cb.obrona_wl = False             # True: w tym obiegu walczymy zamiast uciekać (HP w strefie walki, wróg w zwarciu)
    cb.obrona_bij = {}               # id stwora/gracza z czaszką -> do kiedy bijemy go mimo --potwory
    cb.obrona_blok_do = 0.0          # do kiedy trwa bicie blokującego w trakcie (wstrzymanej) ucieczki
    cb.obrona_robi = False           # True: trwa robienie runy leczenia w walce (_uh_przerwanie nie przerywa z powodu HP/mobów)
    cb.obrona_zapas = None           # (czas, ilość run leczenia, ilość blanków) z ostatniego odczytu plecaków
    cb.obrona_lecz_nast = 0.0        # najwcześniej kolejne użycie runy leczenia
    cb.obrona_lecz_porazki = 0
    cb.obrona_lecz_przerwa = 0.0     # po serii porażek klików runy: do kiedy pomijamy krok 1
    cb.obrona_rob_do = 0.0           # po nieudanym robieniu runy: do kiedy nie ponawiamy
    cb.obrona_blank_do = 0.0         # po "brak blank": do kiedy nie próbujemy (BEZ wyłączania UH na 10 min)
    cb.obrona_log = {}               # klucz -> czas ostatniego logu (throttling)


def _log_raz(cb, klucz, tekst, co_s=10.0, teraz=None):
    c = _c(cb)
    t = cb.zegar() if teraz is None else teraz
    if t - cb.obrona_log.get(klucz, float("-inf")) >= co_s:
        cb.obrona_log[klucz] = t
        c.log(tekst)


def _lista(cb, teraz):
    """Świeża lista stworów (bez peta) na potrzeby oceny przy niskim HP; raz na obieg (cache po `teraz`). Błąd odczytu = lista
    z poprzedniego obiegu. Wołane tylko gdy HP jest niskie albo bije nas ktoś, więc zwykła gra nie płaci dodatkowym odczytem."""
    k = getattr(cb, "obrona_lista", None)
    if k is not None and k[0] == teraz:
        return k[1]
    try:
        lista = cb.stwory()
    except bot.Zatrzymano:
        raise
    except Exception:                              # noqa: BLE001
        lista = getattr(cb, "ostatnie_stwory", None) or []
    cb.obrona_lista = (teraz, lista)
    return lista


def walka_aktywna(cb, teraz):
    """True: tryb obronny trzyma nas w walce: HP w strefie walki, bicie blokującego przy wstrzymanej ucieczce albo aktualny cel to
    ktoś z `obrona_bij` (stwór spoza --potwory / gracz z czaszką, który nas bije). Wtedy strzelamy też runami ataku."""
    if cb.obrona_wl or teraz < cb.obrona_blok_do:
        return True
    cel = cb.cel
    return bool(cel is not None and cb.obrona_bij.get(cel.get("id"), float("-inf")) >= teraz)


def pk_bijemy(cb, s, teraz):
    """True: `s` to gracz z czaszką, którego aktualnie bijemy w obronie (kandydaci() i blok „obcy gracz” traktują go jak cel)."""
    return bool(s.get("gracz")) and cb.obrona_bij.get(s.get("id"), float("-inf")) >= teraz and cb._pk_czaszka(s)


def wrogowie(cb, lista, poz, odl_mob=None):
    """Żywe byty groźne w obronie: dowolny stwór (też spoza --potwory) w <= odl_mob pól oraz gracz Z CZASZKĄ w <= OBRONA_PK_ODL.
    Bez nas, bez peta (lista jest już bez niego), bez widm, bez graczy bez czaszki."""
    c = _c(cb)
    odl_mob = c.OBRONA_WROG_ODL if odl_mob is None else odl_mob
    wynik = []
    for s in cb.bez_widm(lista or ()):
        if s.get("z", poz[2]) != poz[2] or s.get("hp", 100) <= 0:
            continue
        xy = (s["x"], s["y"])
        if xy == tuple(poz[:2]):
            continue
        d = cb.dystans(xy, poz)
        if s.get("gracz"):
            if c.OBRONA_PK_ODL > 0 and d <= c.OBRONA_PK_ODL and cb._pk_czaszka(s):
                wynik.append(s)
        elif d <= odl_mob:
            wynik.append(s)
    return wynik


# --- zapas run (plecaki) -------------------------------------------------------------------------------------------

def zapas(cb, teraz, wiek=3.0):
    """(ilość run leczenia, ilość blanków) z plecaków albo None, gdy odczyt niemożliwy. Cache `wiek` s."""
    c = _c(cb)
    z = cb.obrona_zapas
    if z is not None and teraz - z[0] <= wiek:
        return z[1], z[2]
    try:
        import runa_klik  # noqa: PLC0415
        import uh  # noqa: PLC0415
        if cb.runa_klik_env is None:
            cb.runa_klik_env = runa_klik.SrodowiskoKlik(cb.postac, cb.zapytaj, log=lambda t: c.log(t))
        kont = cb.runa_klik_env.kontenery()
        if not kont:
            return None
        n_l = int(runa_klik._ilosc(kont, int(c.UH_LECZ_RUNA_ID)))
        n_b = int(runa_klik._ilosc(kont, int(uh.UH_BLANK_ID)))
    except bot.Zatrzymano:
        raise
    except Exception as e:                        # noqa: BLE001
        c.log(f"[OBRONA] odczyt plecaków nieudany ({e!r})")
        return None
    cb.obrona_zapas = (teraz, n_l, n_b)
    return n_l, n_b


def lecz_czar(cb):
    """(słowa czaru, klawisz, koszt) czaru robiącego runę LECZENIA na siebie albo None, gdy bot takiego nie ma.
    Najpierw osobne pole UH_LECZ_* (klawisz i koszt > 0). Inaczej UH_CZAR, ale tylko gdy to czar leczący (uh.CZARY:
    adura vita/gran/adura); „adori gran” (HMM) robi runę ataku, więc NIE nadaje się do leczenia."""
    c = _c(cb)
    if c.UH_LECZ_KLAWISZ and int(c.UH_LECZ_KOSZT) > 0:
        return (str(c.UH_LECZ_CZAR) or "runa leczenia"), str(c.UH_LECZ_KLAWISZ), int(c.UH_LECZ_KOSZT)
    import uh  # noqa: PLC0415
    if c.UH_CZAR in uh.CZARY:
        return c.UH_CZAR, str(c.UH_KLAWISZ), int(c.UH_KOSZT)
    return None


def _moze_zrobic(cb, g, z, teraz):
    """Czy da się teraz zrobić runę leczenia w walce: czar jest, >= 1 blank, mana >= koszt, HP nie za niskie, brak karencji."""
    c = _c(cb)
    cz = lecz_czar(cb)
    if cz is None or z is None or z[1] < 1:
        return False
    mana, proc = g.get("mana"), g.get("proc")
    if mana is None or proc is None or mana < cz[2] or proc < c.OBRONA_ROB_RUNE_MIN_HP:
        return False
    return teraz >= cb.obrona_rob_do and teraz >= cb.obrona_blank_do


def sa_srodki(cb, g, teraz):
    """Czy mamy jeszcze czym się leczyć w walce (inaczej HP poniżej OBRONA_OSTATECZNOSC_HP = ostateczność: ucieczka)."""
    c = _c(cb)
    mana = g.get("mana")
    if c.ZDROWIE_CZAR_AKTYWNY and mana is not None and mana >= c.ZDROWIE_CZAR_KOSZT and teraz >= cb.zd_wylaczony_do:
        return True
    z = zapas(cb, teraz)
    if z is None:
        return False
    if z[0] > 0 and teraz >= cb.obrona_lecz_przerwa:
        return True
    return _moze_zrobic(cb, g, z, teraz)


# --- decyzja: walka zamiast ucieczki -------------------------------------------------------------------------------

def ocen(cb, g, poz, teraz, spadek):
    """Wołane w tick() przy progu ucieczki. True = HP jest poniżej progu ucieczki (albo przewidujemy przekroczenie), ale
    walczymy zamiast uciekać (cavebot pomija wejście w ucieczkę)."""
    c = _c(cb)
    cb.obrona_wl = False
    for k in [k for k, v in cb.obrona_bij.items() if v < teraz]:
        del cb.obrona_bij[k]
    proc = g.get("proc")
    if proc is None or cb.pk_stan is not None:
        return False                              # ucieczka PK do depo ma własną obsługę
    gryzie = teraz - cb.hp_gracza_spadek < c.GRYZIE_OKNO
    if not (gryzie or proc <= max(c.OBRONA_BIJ_HP, c.OBRONA_LECZ_HP, cb.prog_aktualny)):
        return False                               # zdrowi i nikt nie bije: zero dodatkowych odczytów
    wr = wrogowie(cb, _lista(cb, teraz), poz)
    if not wr:
        return False
    if gryzie or proc <= c.OBRONA_BIJ_HP:
        for s in wr:
            if cb.dystans((s["x"], s["y"]), poz) > 1:
                continue
            if s.get("gracz") or (cb.potwory is not None and s["nazwa"].casefold() not in cb.potwory):
                if s["id"] not in cb.obrona_bij:
                    c.log(f"[OBRONA] {s['nazwa']} ({s['x']},{s['y']}) stoi obok{' i bije nas' if gryzie else ''} "
                          f"(HP {proc:.0f}%){', gracz z czaszką' if s.get('gracz') else ', poza listą --potwory'}: bijemy go.")
                cb.obrona_bij[s["id"]] = teraz + c.OBRONA_BIJ_S
    prog = cb.prog_aktualny
    hp_niskie = proc <= prog or (spadek > 0 and proc - spadek <= prog)
    if cb.ucieczka or proc > max(c.OBRONA_LECZ_HP, prog):
        return False
    if proc < c.OBRONA_OSTATECZNOSC_HP and not sa_srodki(cb, g, teraz):
        _log_raz(cb, "ostatecznosc", f"[OBRONA] HP {proc:.0f}% < {c.OBRONA_OSTATECZNOSC_HP}% i brak many/run/blanka: "
                 f"ostateczność, uciekam.", 15.0, teraz)
        return False
    cb.obrona_wl = True
    if hp_niskie:
        _log_raz(cb, "zamiast", f"[OBRONA] HP {proc:.0f}% (próg ucieczki {prog:.0f}%), wróg w zwarciu "
                 f"({', '.join(s['nazwa'] for s in wr[:3])}): walczę i leczę się zamiast uciekać.", 10.0, teraz)
    return hp_niskie


def blokada(cb, g, poz, teraz):
    """Wołane, gdy ucieczka TRWA. True = nie uciekamy w tym obiegu, bijemy blokującego: kroki stoją >= OBRONA_BLOK_S, a obok
    jest wróg (dowolny stwór albo gracz z czaszką). Bicie trwa OBRONA_BLOK_WALKA_S s albo do zabicia/odejścia wrogów obok."""
    c = _c(cb)
    if teraz >= cb.obrona_blok_do and teraz - cb.ruch_czas < c.OBRONA_BLOK_S:
        return False                               # ruszamy się: nie ma blokady, bez odczytu
    obok = [s for s in wrogowie(cb, _lista(cb, teraz), poz, 1) if cb.dystans((s["x"], s["y"]), poz) <= 1]
    if teraz < cb.obrona_blok_do:
        if obok:
            for s in obok:
                cb.obrona_bij[s["id"]] = max(cb.obrona_bij.get(s["id"], 0.0), teraz + 2.0)
            return True
        cb.obrona_blok_do = 0.0                   # blokujący zabity/odszedł: ucieczka rusza dalej
        return False
    if not obok or teraz - cb.ruch_czas < c.OBRONA_BLOK_S:
        return False
    cb.obrona_blok_do = teraz + c.OBRONA_BLOK_WALKA_S
    for s in obok:
        cb.obrona_bij[s["id"]] = teraz + c.OBRONA_BLOK_WALKA_S
    c.log(f"[OBRONA] ucieczka stoi {teraz - cb.ruch_czas:.0f} s w miejscu, obok {', '.join(s['nazwa'] for s in obok[:3])}: "
          f"bijemy blokującego zamiast kręcić się w kółko (do {c.OBRONA_BLOK_WALKA_S:.0f} s).")
    return True


def pk_walka(cb, g, poz, teraz):
    """True: nie uruchamiamy ucieczki PK do depo, bo gracz z czaszką stoi w zwarciu (<= OBRONA_PK_ODL) i bije nas albo
    HP <= OBRONA_BIJ_HP, a nie jest to ostateczność. Gracz bez czaszki tu nie istnieje (wrogowie() go pomija)."""
    c = _c(cb)
    if c.OBRONA_PK_ODL <= 0 or cb.pk_stan is not None:
        return False
    proc = g.get("proc", 100.0)
    gryzie = teraz - cb.hp_gracza_spadek < c.GRYZIE_OKNO
    trzymamy = any(v >= teraz for v in cb.obrona_bij.values())          # już bijemy kogoś (histereza: nie uciekamy w pół walki)
    if not (gryzie or proc <= c.OBRONA_BIJ_HP or trzymamy):
        return False
    pk = [s for s in wrogowie(cb, _lista(cb, teraz), poz, 0) if s.get("gracz")]
    if not pk:
        return False
    if proc < c.OBRONA_OSTATECZNOSC_HP and not sa_srodki(cb, g, teraz):
        return False
    for s in pk:
        if cb.dystans((s["x"], s["y"]), poz) <= 1 and s["id"] not in cb.obrona_bij:
            c.log(f"[OBRONA] gracz z czaszką {s['nazwa']} obok (HP {proc:.0f}%): bijemy zamiast uciekać do depo.")
        if cb.dystans((s["x"], s["y"]), poz) <= 1:
            cb.obrona_bij[s["id"]] = teraz + c.OBRONA_BIJ_S
    return True


# --- leczenie w walce ------------------------------------------------------------------------------------------------

def _uzyj_lecz_na_siebie(cb, g):
    """Użycie runy leczenia (UH_LECZ_RUNA_ID) na siebie: ta sama ścieżka co UH na siebie w ucieczce PK (runa_klik.strzel)."""
    import runa_klik  # noqa: PLC0415
    c = _c(cb)
    if cb.runa_klik_env is None:
        cb.runa_klik_env = runa_klik.SrodowiskoKlik(cb.postac, cb.zapytaj, log=lambda t: c.log(t))
    env = cb.runa_klik_env

    class _Sam:                                    # cel = my: weryfikacja po spadku liczby run / wzroście własnego HP
        def __getattr__(s, n):
            return getattr(env, n)

        def hp_celu(s, ident):
            return 100.0

        def hp_wlasne(s):
            return cb.gracz().get("proc")

    kw = {}
    if c.PK_UH_SZYBKIE:
        ctrl = bool(c.PK_UH_CTRL) and cb.pk_uh_ctrl_porazki < c.PK_UH_CTRL_PORAZKI
        kw = dict(szybko=True, ctrl=ctrl, rng=cb.pk_rng, budzet_s=float(c.PK_UH_BUDZET_S),
                  weryfikacja_s=float(c.PK_UH_WERYF_S))
    return runa_klik.strzel(_Sam(), {"id": None, "dx": 0, "dy": 0, "hp": None}, runa_id=int(c.UH_LECZ_RUNA_ID),
                            menu_dx=int(c.RUNA_MENU_DX), menu_dy=int(c.RUNA_MENU_DY), **kw)


def _zrob_lecz_runa(cb, g, teraz):
    """Robi runę leczenia W WALCE (uh.zrob_runa z czarem leczącym; tarcza schodzi z ręki na ok. 4-5 s). BEZ wyłączania UH na
    10 min po „brak blank”: tu wynik tylko odracza kolejną próbę. True = obieg zużyty."""
    import uh  # noqa: PLC0415
    c = _c(cb)
    czar, klawisz, koszt = lecz_czar(cb)
    env = cb._uh_srodowisko()
    uh.ustaw(czar, klawisz=klawisz, koszt=koszt)
    cb.uh_ostatni = teraz
    cb.uh_przerwal_cavebot = None
    cb.aktywnosc_ts = teraz
    cb.ustaw_stan("UH", f"OBRONA: robię runę leczenia {czar} (mana {g.get('mana')}, HP {g.get('proc', 0):.0f}%)")
    c.log(f"[OBRONA] brak runy leczenia w plecaku: robię ją W WALCE ({czar} [{klawisz}], koszt {koszt}, mana {g.get('mana')}, "
          f"HP {g.get('proc', 0):.0f}%).")
    cb.uh_tryb_walki = True
    cb.uh_hp_start = None
    cb.obrona_robi = True
    try:
        wynik = uh.zrob_runa(env, klawisz=klawisz, koszt=koszt)
    finally:
        cb.uh_tryb_walki = False
        cb.obrona_robi = False
        uh.ustaw(c.UH_CZAR, klawisz=c.UH_KLAWISZ, koszt=c.UH_KOSZT)       # _uh i tak ustawia swoje przed każdą runą
    t = cb.zegar()
    cb.uh_ostatni = t
    cb.czar_ostatni = t
    cb.obrona_zapas = None
    w, pw = wynik.get("wynik"), wynik.get("powod")
    c.log(f"[OBRONA] robienie runy leczenia: {w} ({pw}), {wynik.get('czas_s', 0):.0f} s")
    try:
        cb._ml_tele("obrona_runa", wynik=w, powod=str(pw), czas_s=wynik.get("czas_s"), alarm=bool(wynik.get("alarm")))
    except Exception:                              # noqa: BLE001
        pass
    cb.uh_restore = bool(getattr(env, "stan", {}).get("tarcza_id"))      # tarcza poza slotem: _uh przywróci ją w spokoju
    if w == "ok":
        cb.uh_runy += wynik.get("rzuty") or 1
    elif w == "brak_blank":
        cb.obrona_blank_do = t + c.OBRONA_BLANK_PONOW_S
        c.log(f"[OBRONA] brak blanka: UH NIE jest wyłączany, ponowię sprawdzenie za {c.OBRONA_BLANK_PONOW_S:.0f} s "
              f"(teraz exura / ucieczka).")
    else:
        cb.obrona_rob_do = t + c.OBRONA_ROB_PONOW_S
    if wynik.get("alarm"):
        try:
            cb.alarm(f"OBRONA: robienie runy: {pw} (tarcza może być poza slotem)")
        except Exception:                          # noqa: BLE001
            pass
    cb.pauza(0.1, 0.3)
    return True


def lecz_tick(cb, g, poz, teraz):
    """Leczenie w trybie obronnym, PRZED exurą: (1) runa leczenia z plecaka na siebie, (2) brak runy: robimy ją (blank + mana),
    (3)/(4) zwracamy False: exura (_zdrowie_czar_tick, odblokowany poniżej progu ucieczki) i dopiero ostatecznie ucieczka.
    True = obieg zużyty. Błąd nigdy nie wywraca bota."""
    try:
        return _lecz(cb, g, poz, teraz)
    except bot.Zatrzymano:
        raise
    except Exception as e:                         # noqa: BLE001
        _c(cb).log(f"[OBRONA] błąd leczenia {e!r}")
        return False


def _lecz(cb, g, poz, teraz):
    c = _c(cb)
    if not walka_aktywna(cb, teraz):
        return False
    proc = g.get("proc")
    if proc is None or proc > c.OBRONA_LECZ_HP or teraz < cb.obrona_lecz_nast:
        return False
    if cb._czar_blokada() is not None:
        return False
    z = zapas(cb, teraz)
    # krok 1: runa leczenia w plecaku (odczyt niemożliwy = próbujemy, strzel() sam sprawdzi)
    if (z is None or z[0] > 0) and teraz >= cb.obrona_lecz_przerwa:
        cb.obrona_lecz_nast = teraz + c.OBRONA_LECZ_ODSTEP_S
        cb.aktywnosc_ts = teraz
        w = _uzyj_lecz_na_siebie(cb, g)
        cb.obrona_zapas = None
        if w["wynik"] == "ok":
            cb.obrona_lecz_porazki = 0
            cb.runa_ostatni = teraz                # exhaust run: strzał runą ataku czeka swój odstęp
            c.log(f"[OBRONA] runa leczenia na siebie (HP {proc:.0f}%): {w['powod']}")
            cb.pauza(0.05, 0.15)
            return True
        c.log(f"[OBRONA] runa leczenia na siebie bez efektu ({w['wynik']}: {w['powod']})")
        if w["wynik"] != "brak_runy":
            cb.obrona_lecz_porazki += 1
            if cb.obrona_lecz_porazki >= 3:
                cb.obrona_lecz_porazki = 0
                cb.obrona_lecz_przerwa = teraz + 30.0
                c.log("[OBRONA] 3 porażki runy leczenia z rzędu: pomijam ją na 30 s (exura/ucieczka).")
            return False                           # klik się nie udał: exura w tym samym obiegu
        z = (0, z[1]) if z is not None else None      # runy leczenia nie ma; blanków nie znamy, gdy odczyt był niemożliwy
    # krok 2: brak runy w plecaku: robimy ją w walce (wymaga blanka, many >= koszt i czasu CZAR_MIN_PRZERWA_S od ostatniego czaru)
    if _moze_zrobic(cb, g, z, teraz) and teraz - cb.czar_ostatni >= c.CZAR_MIN_PRZERWA_S:
        return _zrob_lecz_runa(cb, g, teraz)
    if z is not None and z[0] <= 0 and z[1] < 1:
        _log_raz(cb, "brak_blank", "[OBRONA] brak runy leczenia i brak blanka: exura / ucieczka (UH nie wyłączany).", 20.0, teraz)
    elif lecz_czar(cb) is None and (z is None or z[0] <= 0):
        _log_raz(cb, "brak_czaru", "[OBRONA] brak runy leczenia, a bot nie ma czaru leczącego (UH_LECZ_* puste, UH_CZAR to czar "
                 "ataku): nie zrobię jej; exura / ucieczka.", 60.0, teraz)
    return False                                   # krok 3: exura w _zdrowie_czar_tick
