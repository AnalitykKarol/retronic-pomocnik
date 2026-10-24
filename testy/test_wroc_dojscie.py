"""Ręczne "Wróć do miasta" (plik WROC) w trakcie DOJŚCIA z depo na spot (24.10, invincible 07:48-07:49): dojście przerywa się
i rusza wyprawa do depo od bieżącej pozycji. Wcześniej `_blokada_startu` zwracała "dojscie" (P7a) także dla ręcznego WROC,
więc zlecenie czekało 180 s w pętli "czekam (postać w walce)" / "(dojscie)", a bot przeszedł całe dojście.
Zostaje bez zmian: automatyczne wyprawy (blanki, cap, jedzenie) nie startują w dojściu; walka/ucieczka/czar/GM/gracz/niskie HP
blokują WROC jak zawsze. Po wyprawie z dojścia mózg nie wraca do przerwanego dojścia (CavebotDojscie.dojscie_wroc).
Atrapy jak w test_wyprawa.py (prawdziwe trasy planów, prawdziwa mapa); nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot
import cavebot
import mapa as _mapa
import mozg
import powiadom as _pw
import wyprawa as W

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test")
    sys.exit(0)
MAPA = _mapa.Mapa()
TMP = Path(tempfile.mkdtemp())
GOB_DO, GOB_Z, _ = W.punkty_bazy(nazwy=W.BAZY_PK)["gobliny_edron"]
GOB_DEPO = tuple(GOB_DO[-1])
GOB_BLISKO = (33167, 31813, 8)          # jak 19e w test_wyprawa: piętro depo Edron, ~20 pól od pola depo
_pw.powiadom = lambda *a, **kw: None


class Konf:
    WYPAD_PO_TORCHE = True
    WYPAD_JEDZENIE = False
    WYPAD_ILE_TORCHY = 5
    WYPAD_ZAKUPY = {"torch": 5}
    WYPAD_SPRAWDZ_S = 15.0
    WYPAD_JEDZENIE_HP = 50.0
    WYPAD_JEDZENIE_SPOKOJ_S = 10.0
    JEDZENIE_ZAPAS_MIN = 5
    JEDZENIE_CZAR_AKTYWNY = 0
    WYPRAWA_AKTYWNA = 0                  # jak bot bez trybu wyprawy: ręczne wywołanie ma działać
    WYPRAWA_ZAPAS_PROG = 0
    WYPRAWA_JEDZENIE_CEL = 20
    WYPRAWA_JEDZENIE_DOKUP = 5
    WYPRAWA_JEDZ_NA_MIEJSCU = 1
    WYPRAWA_JEDZ_MAKS = 12
    WYPRAWA_BLANKI = 0
    WYPRAWA_BLANKI_PROG = 2
    WYPRAWA_BLANKI_MAX_KOSZT = 500
    WYPRAWA_POCHODNIE = 1
    WYPRAWA_CAP_REZERWA = 8
    WYPRAWA_CAP_MIN = 10
    WYPRAWA_ZLOTO_MIN = 30
    WYPRAWA_MIN_HP = 70
    WYPRAWA_CO_MIN = 20
    WYPRAWA_MAX_CZAS_S = 1800
    WYPRAWA_MAX_KROKOW = 6000
    WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CZEKAJ_NA_GLOD = 0
    WYPRAWA_WZNOW_WALIDUJ = 1
    WYPRAWA_TYLKO_DEPO = 0
    UH_STAN_PLIK = None


class Swiat:
    def __init__(s, poz, hp=100):
        s.poz = list(poz)
        s.t = 1000.0
        s.wall = 5_000_000.0
        s.hp = hp
        s.plecak = {3003: 1, 3582: 9, 3031: 500, 2920: 5}
        s.stwory = []
        s.cel = None
        s.mowa = []
        s.zdarzenia = []
        s.alarmy = []

    def gracz(s):
        return {"hp": s.hp, "max_hp": 100, "proc": float(s.hp), "cap": 300.0, "max_cap": 400.0, "mana": 50, "max_mana": 95}


class Postac:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def krok(p, k):
        d = bot.KIERUNKI[k]
        p.s.t += 0.2
        p.s.poz[:] = [p.s.poz[0] + d[0], p.s.poz[1] + d[1], p.s.poz[2]]
        return tuple(p.s.poz)

    def klawisz(p, k):
        pass


class CB:
    """Cavebot w pigułce (jak w test_wyprawa.py) + flaga dojscie_aktywne jak w CavebotDojscie."""
    dojscie_aktywne = False
    dojscie_wroc = False

    def __init__(c, s, dojscie):
        c.s = s
        c.dojscie_aktywne = dojscie
        c.mapa = MAPA
        c.postac = Postac(s)
        c.cel = None
        c.ucieczka = False
        c.ostrozny = False
        c.w_poscigu = False
        c.pamiec = None
        c.w_lootcie = False
        c.lww = None
        c.lww_zalegle = None
        c.zwloki_czekajace = []
        c.stan = "IDZ"
        c.ruch_poz = tuple(s.poz)
        c.ostatnie_stwory = []
        c.prog_aktualny = 30
        c.jedzenie_plecak = None
        c.jedzenie_nie_do = float("-inf")
        c.wypad_aktywny = False
        c.wypad_czat = None
        c.sciany = set()
        c.zablokowane = set()
        c.potwory = None
        c.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: s.zdarzenia.append((typ, d)))
        c.alarm = lambda t: s.alarmy.append(t)
        c.wroty = []
        c.uh_restore = False
        c.zd_oczekuje = None

    def zegar(c):
        return c.s.t

    def spij(c, d):
        c.s.t += d

    def pauza(c, a=0.1, b=0.3):
        c.s.t += (a + b) / 2

    def gracz(c):
        return c.s.gracz()

    def ustaw_stan(c, a, b=""):
        c.stan = a

    def _wypad_reset_klik(c):
        pass

    def _zywe_w_promieniu(c, lista, poz, odl):
        return [m for m in lista or [] if not m.get("gracz") and m.get("z") == poz[2] and m.get("hp", 100) > 0
                and max(abs(m["x"] - poz[0]), abs(m["y"] - poz[1])) <= odl]

    def droga(c, od, do, dlugosc=0):
        return []

    def krok_do(c, cel):
        sw = c.s
        sw.t += 0.3
        if len(cel) > 2 and cel[2] == sw.poz[2] and max(abs(sw.poz[0] - cel[0]), abs(sw.poz[1] - cel[1])) == 1:
            sw.poz[:] = [cel[0], cel[1], cel[2]]

    def _idz_odcinek(c, punkty, idx):
        s = c.s
        s.t += 0.6
        idx = min(idx + 1, len(punkty) - 1)
        p = punkty[idx]
        if p[2] == s.poz[2]:
            s.poz[:] = list(p)
        return True, idx

    def _wypad_wroc_na_trase(c, poz):
        c.wroty.append(tuple(poz))
        return True

    def jedzenie_znane_brak(c, teraz):
        return teraz < c.jedzenie_nie_do

    def _czar_blokada(c):
        return None


class Ops:
    id_przedmiotow = {"torch": {2920}, "ham": {3582}, "blank": {3147}}
    id_jedzenia = {3582, 3577, 3607}

    def __init__(o, s):
        o.s = s

    def ekwipunek(o):
        return {10: 2925}

    def plecak(o):
        return {"id": {k: v for k, v in o.s.plecak.items() if v > 0}}

    def wiadomosci(o):
        return []

    def czat(o, t):
        o.s.mowa.append(t)

    def uzyj_pole(o, pole, poz):
        pass

    def uzyj_line(o, cel, poz):
        pass


_n = [0]


def swiat(dojscie=True, poz=GOB_BLISKO, hp=100):
    _n[0] += 1
    s = Swiat(poz, hp=hp)
    cb = CB(s, dojscie)
    ops = Ops(s)
    logi = []
    ops.log = logi.append
    w = W.Wyprawa(cb, ops, konf=Konf(), log=logi.append, plik_stanu=TMP / f"stan{_n[0]}.json",
                  plik_sklepow=TMP / "brak_sklepow.json", plik_npc=TMP / f"npc{_n[0]}.json",
                  plik_stop=TMP / f"STOP{_n[0]}", czas=lambda: s.wall)
    w.logi = logi
    cb.ruch_poz = tuple(s.poz)
    w._plik_wroc().write_text("")              # zlecenie: ./wroc.sh
    return s, cb, w


def tyk(s, cb, w, dt=1.0):
    s.t += dt
    s.wall += dt
    cb.ruch_poz = tuple(s.poz)
    cb.ostatnie_stwory = list(s.stwory)
    cb.cel = s.cel
    return w._okazja(s.t)


def bieg(s, cb, w, maks=12000):
    start = False
    for i in range(maks):
        s.t += 0.3
        s.wall += 0.3
        cb.ruch_poz = tuple(s.poz)
        cb.ostatnie_stwory = list(s.stwory)
        cb.cel = s.cel
        w.tick()
        if w.aktywny:
            start = True
        elif start:
            return i, True
    return maks, start


def mob(dx=2, dy=0, poz=GOB_BLISKO):
    return {"id": 77, "nazwa": "Troll", "x": poz[0] + dx, "y": poz[1] + dy, "z": poz[2], "hp": 100}


def gracz_obcy(dx=3, dy=0, poz=GOB_BLISKO):
    return {"id": 78, "nazwa": "Obcy", "gracz": True, "x": poz[0] + dx, "y": poz[1] + dy, "z": poz[2], "hp": 100}


# --- 1. sedno: WROC w dojściu rusza wyprawę od bieżącej pozycji ---------------------------------------------------------
s, cb, w = swiat(dojscie=True)
start = tyk(s, cb, w)
sprawdz("1a WROC w dojściu (spokój): jeden obieg startuje wyprawę 'depo:reczny' od bieżącej pozycji",
        start and cb.wypad_aktywny and w.powod == "wyprawa:depo:reczny" and w.w["potrzeby"] == {"depo": True, "reczny": True}
        and tuple(w.w["stops"][0]["stoi"]) == GOB_DEPO, (start, w.powod, w.logi[-3:]))
sprawdz("1b plik WROC znika po ruszeniu, zlecenie rozliczone", not w._plik_wroc().exists() and w._wroc_od is None)
sprawdz("1c cavebot dostaje znacznik dojscie_wroc (dojście nie wróci po wyprawie)", cb.dojscie_wroc is True)
sprawdz("1d log: komunikat o przerwaniu dojścia", any("przerywam dojście" in l for l in w.logi), w.logi[-5:])

# --- 2. bez dojścia nic się nie zmienia (pętla): znacznik nie powstaje ------------------------------------------------------
s2, cb2, w2 = swiat(dojscie=False)
sprawdz("2a WROC na pętli startuje jak dotąd, bez znacznika dojścia", tyk(s2, cb2, w2) and cb2.wypad_aktywny and cb2.dojscie_wroc is False)

# --- 3. automatyczne wyprawy w dojściu nadal zablokowane (P7a) --------------------------------------------------------------
s3, cb3, w3 = swiat(dojscie=True)
poz3 = tuple(s3.poz)
sprawdz("3a _blokada_startu (automat) w dojściu = 'dojscie'", w3._blokada_startu(s3.t, poz3, []) == "dojscie")
sprawdz("3b _blokada_startu (automat, w walce) w dojściu = 'dojscie'", w3._blokada_startu(s3.t, poz3, [], True) == "dojscie")
sprawdz("3c _blokada_startu ręczna w dojściu = None (spokój)", w3._blokada_startu(s3.t, poz3, [], reczny=True) is None)
w3._plik_wroc().unlink()
w3.konf.WYPRAWA_AKTYWNA = 1
sprawdz("3d bez pliku WROC wyzwalacz automatyczny w dojściu nie startuje",
        not tyk(s3, cb3, w3, 40.0) and not cb3.wypad_aktywny and not cb3.dojscie_wroc)
s3b, cb3b, w3b = swiat(dojscie=False)
sprawdz("3e poza dojściem blokada automatu bez zmian (spokój = None)", w3b._blokada_startu(s3b.t, tuple(s3b.poz), []) is None)


# --- 4. bezpieczniki WROC w dojściu: jak na pętli -------------------------------------------------------------------------
def trzyma(opis, przygotuj):
    s, cb, w = swiat(dojscie=True)
    przygotuj(s, cb, w)
    wyn = [tyk(s, cb, w) for _ in range(4)]
    sprawdz(f"4 {opis}: WROC w dojściu czeka, wyprawa nie startuje, plik zostaje",
            not any(wyn) and not cb.wypad_aktywny and w._plik_wroc().exists() and not cb.dojscie_wroc, (wyn, w.logi[-2:]))


def walka(s, cb, w):
    s.cel = {"id": 77}


trzyma("walka (cel)", walka)
trzyma("ucieczka", lambda s, cb, w: setattr(cb, "ucieczka", True))
trzyma("tryb ostrożny", lambda s, cb, w: setattr(cb, "ostrozny", True))
trzyma("pościg", lambda s, cb, w: setattr(cb, "w_poscigu", True))
trzyma("loot", lambda s, cb, w: setattr(cb, "w_lootcie", True))
trzyma("czar w toku", lambda s, cb, w: setattr(cb, "zd_oczekuje", 1))
trzyma("niskie HP", lambda s, cb, w: setattr(s, "hp", 50))
trzyma("GM (alarm czatu)", lambda s, cb, w: setattr(cb, "wypad_czat", types.SimpleNamespace(zablokowany=True)))
trzyma("obcy gracz obok", lambda s, cb, w: s.stwory.append(gracz_obcy()))
trzyma("wyprawa zablokowana po STOP", lambda s, cb, w: setattr(w, "zablokowany", True))
s, cb, w = swiat(dojscie=True)
cb.wypad_aktywny = True
wyn = [tyk(s, cb, w) for _ in range(4)]
sprawdz("4 trwa wypad: WROC w dojściu nie startuje drugiej wyprawy, plik zostaje", not any(wyn) and w.w is None
        and w._plik_wroc().exists() and not cb.dojscie_wroc, (wyn, w.logi[-2:]))

# potwory w pobliżu: dojście i tak biegnie przez nie, więc nie blokują ręcznego WROC; na pętli blokują jak dziś
s, cb, w = swiat(dojscie=True)
s.stwory.append(mob())
sprawdz("4m potwór 2 pola obok w dojściu NIE blokuje WROC (dojście biegnie przez moby, inaczej czekałoby do limitu)",
        tyk(s, cb, w) and cb.wypad_aktywny and cb.dojscie_wroc, w.logi[-2:])
s, cb, w = swiat(dojscie=False)
s.stwory.append(mob())
wyn = [tyk(s, cb, w) for _ in range(3)]
sprawdz("4n potwór obok na pętli blokuje WROC jak dziś ('moby')", not any(wyn) and not cb.wypad_aktywny
        and any("moby" in l for l in w.logi), w.logi[-2:])

# walka najpierw, potem idzie: po zakończeniu walki w dojściu wyprawa rusza
s, cb, w = swiat(dojscie=True)
s.cel = {"id": 77}
a = tyk(s, cb, w)
s.cel = None
b = tyk(s, cb, w)
sprawdz("4o walka w dojściu: najpierw czeka, po walce rusza", (not a) and b and cb.wypad_aktywny and cb.dojscie_wroc, (a, b))

# --- 5. wyprawa z dojścia dochodzi do depo, STOP, bez zakupów i bez powrotu na spot --------------------------------------
s, cb, w = swiat(dojscie=True)
plecak0 = dict(s.plecak)
tyk(s, cb, w)
n, wyst = bieg(s, cb, w)
kon = [d for t, d in s.zdarzenia if t == "wyprawa_koniec"]
sprawdz("5a wyprawa z dojścia: koniec 'depo' w polu depo, STOP w pliku, brak zakupów i powrotu na spot",
        wyst and tuple(s.poz) == GOB_DEPO and kon and kon[-1]["wynik"] == "depo" and w.plik_stop.exists() and w.w is None
        and not cb.wypad_aktywny and s.mowa == [] and s.plecak == plecak0 and not s.alarmy, (s.poz, kon, s.alarmy))
sprawdz("5b po depo wyprawa zablokowana (żadnych samoczynnych), plik WROC nie wrócił", w.zablokowany and not w._plik_wroc().exists())

# --- 6. CavebotDojscie: po wyprawie z dojścia nie wraca do przerwanego dojścia ------------------------------------------------
_stary_tick = cavebot.Cavebot.tick
cavebot.Cavebot.tick = lambda self: "super"
_stare_log = cavebot.log
cavebot.log = lambda *a: None
try:
    cd = cavebot.CavebotDojscie.__new__(cavebot.CavebotDojscie)
    cd.postac = types.SimpleNamespace(pozycja=lambda: (33167, 31813, 8))
    cd.punkty = [(33167, 31813, 8), (33000, 31700, 8), (33000, 31600, 7)]
    cd.idx = 0
    cd.dojscie_ok = False
    cd.dojscie_porazka = False
    cd.dojscie_tol = 2
    cd._dojscie_cel = cd.punkty[-1]
    cd._dojscie_prev = 0
    cd._dojscie_start = cd.punkty[0]
    cd.wypad_aktywny = False
    sprawdz("6a domyślnie dojscie_wroc=False i zwykłe dojście dalej woła tick cavebota",
            getattr(cavebot.CavebotDojscie, "dojscie_wroc", None) is False and cd.tick() == "super")
    cd.dojscie_wroc = True
    cd.wypad_aktywny = True
    sprawdz("6b dojscie_wroc + wyprawa trwa: tick idzie dalej (wyprawa prowadzi ruch)", cd.tick() == "super")
    cd.wypad_aktywny = False
    sprawdz("6c dojscie_wroc + wyprawa skończona: dojście się kończy (False), nie wraca na trasę dojścia", cd.tick() is False)
    sprawdz("6d to nie porażka ani sukces dojścia", cd.dojscie_ok is False and cd.dojscie_porazka is False)
finally:
    cavebot.Cavebot.tick = _stary_tick
    cavebot.log = _stare_log


# --- 7. mozg.przejdz_dojscie: bez ponawiania po wyprawie z dojścia, znacznik dla main ------------------------------------------
class FP:
    poz = (10, 10, 7)

    def pozycja(s):
        return s.poz


proby = []


class FabWroc:
    def __init__(s, postac, punkty, okr, czas, hp, jedz, potw, gracze, **kw):
        s.postac, s.punkty = postac, punkty
        s.dojscie_wroc = False
        proby.append(s)

    def uruchom(s):
        s.dojscie_wroc = True                    # wyprawa z WROC wystartowała i skończyła się (np. STOP w depo)
        s.postac.poz = (20, 20, 7)


wyn = mozg.przejdz_dojscie(FP(), [[10, 10, 7], [50, 50, 7]], fabryka=FabWroc, proby=3)
sprawdz("7a po wyprawie z dojścia przejdz_dojscie zwraca False i NIE ponawia dojścia", wyn is False and len(proby) == 1, len(proby))
sprawdz("7b znacznik dla main: dojscie_przerwane_wroc()", mozg.dojscie_przerwane_wroc() is True)


class FabBez(FabWroc):
    def uruchom(s):
        s.postac.poz = (10, 10, 7)               # zwykła porażka dojścia


proby.clear()
wyn = mozg.przejdz_dojscie(FP(), [[10, 10, 7], [50, 50, 7]], fabryka=FabBez, proby=3)
sprawdz("7c zwykła porażka dojścia: dalej ponawia (3 próby), znacznik wyczyszczony",
        wyn is False and len(proby) == 3 and mozg.dojscie_przerwane_wroc() is False, len(proby))

# --- 8. mozg.main: decyzja po dojściu przerwanym przez WROC ------------------------------------------------------------------------
_stop_stary = bot.STOP
bot.STOP = TMP / "STOP_main"
try:
    logm = []
    mozg._dojscie_wroc_przerwane = False
    sprawdz("8a bez znacznika: main nie przejmuje decyzji", mozg.po_dojsciu_przez_wroc(logm.append) is False)
    mozg._dojscie_wroc_przerwane = True
    sprawdz("8b znacznik bez STOP (wyprawa skończyła się bez STOP): main dalej według starych reguł (blisko trasy / powiadomienie)",
            mozg.po_dojsciu_przez_wroc(logm.append) is False)
    bot.STOP.write_text("wyprawa: dotarłem do depo\n")
    sprawdz("8c znacznik + STOP w depo: main kończy proces cicho (bez powiadomienia 'dojście nieudane')",
            mozg.po_dojsciu_przez_wroc(logm.append) is True and any("Wróć do miasta" in l for l in logm), logm)
finally:
    bot.STOP = _stop_stary
    mozg._dojscie_wroc_przerwane = False

src = Path(mozg.__file__).read_text()
i_po = src.index("po_dojsciu_przez_wroc(log)")
i_ratunek = src.index('ratunek_porazka(postac, "dojscie"')
i_krytyczne = src.index("Bot: dojście na spot nieudane")
sprawdz("8d main woła po_dojsciu_przez_wroc PRZED ratunek_porazka i powiadomieniem critical", i_po < i_ratunek < i_krytyczne,
        (i_po, i_ratunek, i_krytyczne))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
