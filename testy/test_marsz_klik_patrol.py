#!/usr/bin/env python3
"""20.10: marsz klikiem w patrolu/dojściu (cavebot._marsz_klik, pokrętła MARSZ_KLIK i MARSZ_KLIK_MAKS_POL).

Atrapa świata z zegarem wirtualnym: klient po kliku idzie sam (jedno pole na krok_t s, najpierw w poziomie), Escape go zatrzymuje,
klawisz ruchu też; można mu kazać stać (klik bez skutku) albo przenieść postać na inne piętro. Bez gry, bez gniazd, bez X11."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types
import random
import json
import tempfile
import pathlib
from collections import deque
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import bot
import pokretla as _pk

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(str(x) for x in a))
cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.TRYB_PATROL = 0
Z = 8


class Mapa:
    """Płaski plac x 90..140, y 40..60 na piętrze Z; `nad` nadpisuje flagi pól (3 = schody/dziura, 5 = ściana)."""
    def __init__(m, nad=None):
        m.nad = dict(nad or {})

    def flagi(m, x, y, z):
        if (x, y, z) in m.nad:
            return m.nad[(x, y, z)]
        return 1 if (z == Z and 90 <= x <= 140 and 40 <= y <= 60) else 0

    def przechodnie(m, x, y, z):
        f = m.flagi(x, y, z)
        return None if not f & 1 else not f & 4

    def droga(m, start, cel, zajete=(), dlugosc=1, skosy=True, **k):
        z = start[2]
        zaj = {tuple(p[:2]) for p in zajete}
        st, c = tuple(start[:2]), tuple(cel[:2])
        kol, skad = deque([st]), {st: None}
        while kol:
            p = kol.popleft()
            if max(abs(p[0] - c[0]), abs(p[1] - c[1])) <= dlugosc:
                wyn = []
                while skad[p] is not None:
                    wyn.append((p[0], p[1], z))
                    p = skad[p]
                return wyn[::-1]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (p[0] + dx, p[1] + dy)
                f = m.flagi(q[0], q[1], z)
                if q in skad or q in zaj or not f & 1 or f & 4 or (f & 2 and q != c):
                    continue
                skad[q] = p
                kol.append(q)
        return None


class Swiat:
    def __init__(s, poz, krok_t=0.25):
        s.t = 0.0
        s.poz = list(poz)
        s.krok_t = krok_t
        s.cel = None
        s.acc = 0.0
        s.stoi = False               # klient ignoruje kliki
        s.blok = set()
        s.stwory = []
        s.ev = []                    # ("klik", (x, y)) / ("klawisz", nazwa) / ("atak", id)
        s.teleport = None            # (t, nowa poz)
        s.hp = 100

    def adv(s, dt):
        s.t += dt
        if s.teleport and s.t >= s.teleport[0]:
            s.poz[:] = list(s.teleport[1])
            s.cel, s.teleport = None, None
        if s.cel is None or s.stoi:
            s.acc = 0.0
            return
        s.acc += dt
        while s.acc >= s.krok_t and s.cel is not None:
            s.acc -= s.krok_t
            dx = (s.cel[0] > s.poz[0]) - (s.cel[0] < s.poz[0])
            dy = (s.cel[1] > s.poz[1]) - (s.cel[1] < s.poz[1])
            if not dx and not dy:
                s.cel = None
                break
            n = (s.poz[0] + dx, s.poz[1]) if dx else (s.poz[0], s.poz[1] + dy)
            if n in s.blok:
                s.cel = None
                break
            s.poz[0], s.poz[1] = n
            if (s.poz[0], s.poz[1]) == s.cel:
                s.cel = None

    def zegar(s):
        return s.t

    def spij(s, d):
        s.adv(d)

    def zapytaj(s, z):
        s.adv(0.05)
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        return {}

    def klik(s, dx, dy):
        c = (s.poz[0] + dx, s.poz[1] + dy)
        s.ev.append(("klik", c))
        if not s.stoi:
            s.cel = c
        s.adv(0.05)

    def klawisze(s):
        return [e[1] for e in s.ev if e[0] == "klawisz"]

    def kliki(s):
        return [e[1] for e in s.ev if e[0] == "klik"]


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        s = p.s
        s.ev.append(("klawisz", k))
        s.cel = None
        d = bot.KIERUNKI.get(k)
        s.adv(0.2)
        if d is None:
            return
        n = (s.poz[0] + d[0], s.poz[1] + d[1])
        if n not in s.blok:
            s.poz[0], s.poz[1] = n

    def krok(p, k):
        p.klawisz(k)
        return tuple(p.s.poz)


def nowy(poz, seg=None, mapa=None, **kw):
    """-> (świat, cavebot z punktami = odcinek patrolu `seg` (lista (x, y, z)), od pola obok `poz`)."""
    s = Swiat(poz)
    if seg is None:
        seg = [(poz[0] + i, poz[1], Z) for i in range(1, 21)]

    def atak(m, g):
        s.ev.append(("atak", m["id"]))
        for x in s.stwory:
            if x["id"] == m["id"]:
                x["hp"] -= 50
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    b = cavebot.Cavebot(P(s), seg, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, mapa=mapa or Mapa(), klik=s.klik, czas_s=10 ** 7, **kw)
    b.wpadniecie = SimpleNamespace(dziury=set(), lista=lambda *a, **k: [], obserwuj=lambda *a: None, tick=lambda *a: None)
    b.drzwi_def = []
    b.punkty = [tuple(p) for p in seg] + [tuple(seg[-1])] * 10
    b.idx = 0
    b.otwarta = True
    b.__dict__["_w_segmencie"] = True        # jak w _idz_segment (patrol)
    b.stan = "IDZ"
    return s, b


def marsz(b, n=1):
    """n obiegów hooka na bieżącej pozycji (jak _idz_trasa po zaliczeniu osiągniętych punktów)."""
    r = None
    for _ in range(n):
        poz = b.postac.pozycja()
        while b.idx < len(b.punkty) and tuple(b.punkty[b.idx][:2]) == tuple(poz[:2]):
            b.idx += 1
        r = b._marsz_klik(poz, None)
    return r


def czy_kliki(s):
    return s.kliki()


# ---------- 0. pokrętła ----------
sprawdz("0a MARSZ_KLIK domyślnie 0, MAKS_POL 5", cavebot.MARSZ_KLIK == 0 and cavebot.MARSZ_KLIK_MAKS_POL == 5)
sprawdz("0b zakresy pokręteł 0-1 i 2-7, kierunek nie_wyzej",
        _pk.ZAKRESY.get("MARSZ_KLIK") == (0, 1) and _pk.ZAKRESY.get("MARSZ_KLIK_MAKS_POL") == (2, 7)
        and _pk.KIERUNEK.get("MARSZ_KLIK") == "nie_wyzej" and _pk.KIERUNEK.get("MARSZ_KLIK_MAKS_POL") == "nie_wyzej")
_ok, _bl = _pk.waliduj({"MARSZ_KLIK": 1, "MARSZ_KLIK_MAKS_POL": 7})
_ok2, _bl2 = _pk.waliduj({"MARSZ_KLIK_MAKS_POL": 8})
sprawdz("0c walidacja: 1 i 7 ok, 8 odrzucone", _ok == {"MARSZ_KLIK": 1, "MARSZ_KLIK_MAKS_POL": 7} and _bl2 and not _ok2, (_ok, _bl2))
_przyklad = json.loads((pathlib.Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) / "na_zywo.przyklad.json").read_text())
sprawdz("0d na_zywo.przyklad.json ma oba pokrętła z wartościami domyślnymi",
        _przyklad.get("MARSZ_KLIK") == 0 and _przyklad.get("MARSZ_KLIK_MAKS_POL") == 5, _przyklad.get("MARSZ_KLIK"))
_tmp = pathlib.Path(tempfile.mkdtemp()) / "na_zywo.json"
_pr = _pk.Pokretla(cavebot, plik=_tmp, log=lambda *a: None)
_tmp.write_text(json.dumps({"MARSZ_KLIK": 1, "MARSZ_KLIK_MAKS_POL": 3}))
_pr.odswiez()
sprawdz("0e hot-reload ustawia stałe cavebota", cavebot.MARSZ_KLIK == 1 and cavebot.MARSZ_KLIK_MAKS_POL == 3,
        (cavebot.MARSZ_KLIK, cavebot.MARSZ_KLIK_MAKS_POL))
_tmp.write_text("{}")
_pr.mtime = None
_pr.odswiez()
sprawdz("0f usunięcie kluczy = powrót do domyślnych", cavebot.MARSZ_KLIK == 0 and cavebot.MARSZ_KLIK_MAKS_POL == 5,
        (cavebot.MARSZ_KLIK, cavebot.MARSZ_KLIK_MAKS_POL))

# ---------- 1. MARSZ_KLIK=0: zachowanie bez zmian (hak nie jest nawet wołany) ----------
cavebot.MARSZ_KLIK = 0
wolany = []
oryginal = cavebot.Cavebot._marsz_klik
cavebot.Cavebot._marsz_klik = lambda self, *a, **k: wolany.append(1)
LOGI.clear()
random.seed(5)
s, b = nowy((100, 50, Z))
for _ in range(60):
    b._idz_trasa()
sprawdz("1a przy 0 hak _marsz_klik nie jest wołany, marsz niezaczęty", not wolany and b.marsz is None, wolany)
sprawdz("1b przy 0 brak linii [MARSZ] w logu", not any("[MARSZ]" in l for l in LOGI), LOGI[:3])
sprawdz("1c przy 0 postać idzie jak dotąd (klikiem po punktach trasy, dochodzi dalej niż 8 pól)", s.poz[0] >= 108 and s.kliki(), (s.poz, len(s.kliki())))
cavebot.Cavebot._marsz_klik = oryginal
# dozwolony tylko w patrolu/dojściu i tylko z włączonym pokrętłem
cavebot.MARSZ_KLIK = 1
s, b = nowy((100, 50, Z))
sprawdz("1d przy 1 w odcinku patrolu marsz dozwolony", b._marsz_dozwolony())
b.__dict__["_w_segmencie"] = False
sprawdz("1e przy 1 poza patrolem i dojściem (zwykła trasa) marsz niedozwolony", not b._marsz_dozwolony())
b.__dict__["_w_segmencie"] = True
b.wypad_aktywny = True
sprawdz("1f w wypadzie niedozwolony", not b._marsz_dozwolony())
b.wypad_aktywny = False
cavebot.MARSZ_KLIK = 0
sprawdz("1g przy 0 niedozwolony", not b._marsz_dozwolony())
cavebot.MARSZ_KLIK = 1
sd = cavebot.CavebotDojscie(P(s), [(100 + i, 50, Z) for i in range(1, 21)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                            spij=s.spij, zegar=s.zegar, loot=None, mapa=Mapa(), klik=s.klik, czas_s=10 ** 7)
sprawdz("1h w dojściu (CavebotDojscie) marsz dozwolony", sd._marsz_dozwolony())

# ---------- 2. klik tylko na odcinku zwykłych pól ----------
cavebot.MARSZ_KLIK = 1
cavebot.MARSZ_KLIK_MAKS_POL = 5
LOGI.clear()
s, b = nowy((100, 50, Z))
r = marsz(b)
sprawdz("2a zwykły korytarz: klik 5 pól naprzód (105,50), obieg zużyty", r is True and s.kliki() == [(105, 50)], (r, s.kliki()))
sprawdz("2b log [MARSZ] klik na (105, 50) 5 pól", any(l.startswith("[MARSZ] klik na (105, 50) 5 pól") for l in LOGI), LOGI)
sprawdz("2c stan marszu zapamiętany (cel, n, piętro)", b.marsz and b.marsz["cel"] == (105, 50) and b.marsz["n"] == 5 and b.marsz["z"] == Z)

cavebot.MARSZ_KLIK_MAKS_POL = 3
s, b = nowy((100, 50, Z))
marsz(b)
sprawdz("2d MARSZ_KLIK_MAKS_POL=3 -> klik 3 pola naprzód", s.kliki() == [(103, 50)], s.kliki())
cavebot.MARSZ_KLIK_MAKS_POL = 7
s, b = nowy((100, 50, Z))
marsz(b)
sprawdz("2e MAKS_POL=7 -> klik nie dalej niż widok (±6 pól z zapasem): 106", s.kliki() == [(106, 50)], s.kliki())
cavebot.MARSZ_KLIK_MAKS_POL = 5

# pełny marsz korytarza 30 pól: kilka kliknięć, zero klawiszy, dochodzi
s, b = nowy((100, 50, Z), [(100 + i, 50, Z) for i in range(1, 31)])
LOGI.clear()
for _ in range(400):
    marsz(b)
    if tuple(s.poz[:2]) == (130, 50):
        break
sprawdz("2f korytarz 30 pól: dochodzimy klikami, bez klawiszy", tuple(s.poz[:2]) == (130, 50) and not s.klawisze(),
        (s.poz, s.klawisze()[:3]))
sprawdz("2g 30 pól to 6 kliknięć po 5 pól (nie 30 kroków)", len(s.kliki()) == 6, s.kliki())
sprawdz("2h logi wyników: 'doszedł' dla odcinków", sum("[MARSZ] doszedł na" in l for l in LOGI) >= 5, LOGI[:6])

# minimum 2 pola: jedno pole to zwykły krok
s, b = nowy((100, 50, Z), [(101, 50, Z)])
sprawdz("2i odcinek z 1 polem: bez kliku (None), zwykła ścieżka", marsz(b) is None and not s.kliki())

# ---------- 3. schody, ogień, zajęte pole, dziura skracają odcinek ----------
# 3a schody (flaga 3) w (104,51): pola 103..105 w jego sąsiedztwie odpadają -> klik tylko do 102
s, b = nowy((100, 50, Z), mapa=Mapa({(104, 51, Z): 3}))
marsz(b)
sprawdz("3a schody obok drogi (sąsiedztwo): odcinek kończy się przed nimi (102,50)", s.kliki() == [(102, 50)], s.kliki())
# 3b schody na samej drodze (flaga 3 na (103,50)): klik do 101 (102 sąsiaduje)
s, b = nowy((100, 50, Z), mapa=Mapa({(103, 50, Z): 3}))
r = marsz(b)
sprawdz("3b schody na drodze: 1 pole bezpieczne (101) = za mało, bez kliku", r is None and not s.kliki(), (r, s.kliki()))
# 3c schody dalej: (106,50) -> sąsiedztwo 105..107 odpada -> klik do 104
s, b = nowy((100, 50, Z), mapa=Mapa({(106, 50, Z): 3}))
marsz(b)
sprawdz("3c schody na 106: klik do 104", s.kliki() == [(104, 50)], s.kliki())
# 3d schody w prostokącie, ale nie przy drodze (klient mógłby skrócić): trasa łukiem
seg_luk = [(100, 50, Z), (100, 49, Z), (101, 49, Z), (102, 49, Z), (103, 49, Z), (104, 49, Z)]
s, b = nowy((100, 50, Z), seg_luk[1:], mapa=Mapa({(102, 50, Z): 3}))
marsz(b)
sprawdz("3d flaga 2 w prostokącie poz-cel (klient mógłby iść przez nią): klik skrócony poza ten prostokąt",
        not s.kliki() or all(c[0] < 102 or c == (101, 49) for c in s.kliki()), s.kliki())
# 3e ściana (flaga 5) na drodze
s, b = nowy((100, 50, Z), mapa=Mapa({(104, 50, Z): 5}))
marsz(b)
sprawdz("3e ściana na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3f pole nieznane mapie
s, b = nowy((100, 50, Z), mapa=Mapa({(104, 50, Z): 0}))
marsz(b)
sprawdz("3f pole nieznane (flaga 0) na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3g ogień bieżący na 104
s, b = nowy((100, 50, Z))
b.ogien_pola = {(104, 50, Z): 1}
marsz(b)
sprawdz("3g bieżący ogień na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3h maska stała ognia (ogien_stale) na 104, bez bieżącego ognia
s, b = nowy((100, 50, Z))
b.ogien_stale = {(104, 50, Z)}
marsz(b)
sprawdz("3h maska stała ognia na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3i ogień w prostokącie, obok drogi (klient mógłby iść przez niego)
s, b = nowy((100, 50, Z), seg_luk[1:])
b.ogien_pola = {(102, 50, Z): 1}
marsz(b)
sprawdz("3i ogień w prostokącie poz-cel: klik nie obejmuje go", all(not (c[0] >= 102) for c in s.kliki()), s.kliki())
# 3j zajęte pole: moster stoi na 105
s, b = nowy((100, 50, Z))
s.stwory = [{"id": 7, "nazwa": "Rat", "gracz": False, "x": 105, "y": 50, "z": Z, "hp": 100}]
b.potwory = {"nigdy"}                      # nie jest celem do walki (inna lista), ale zajmuje pole
marsz(b)
sprawdz("3j pole 105 zajęte przez stwora: klik do 104", s.kliki() == [(104, 50)], s.kliki())
# 3k gracz na 103 -> klik tylko 101..102 (min 2 pola = 102)
s, b = nowy((100, 50, Z))
s.stwory = [{"id": 8, "nazwa": "Obcy", "gracz": True, "x": 103, "y": 50, "z": Z, "hp": 100}]
marsz(b)
sprawdz("3k gracz na 103: klik do 102", s.kliki() == [(102, 50)], s.kliki())
# 3l widmo (wpis-widmo) nie zajmuje pola (STWORY_WIDMA=0: stwory() nie przelicza znaczników, wpis ma `widmo` od rdzenia/atrapy)
s, b = nowy((100, 50, Z))
s.stwory = [{"id": 9, "nazwa": "Duch", "gracz": True, "x": 103, "y": 50, "z": Z, "hp": 100, "widmo": "duplikat_pola"}]
cavebot.STWORY_WIDMA = 0
marsz(b)
cavebot.STWORY_WIDMA = 1
sprawdz("3l wpis-widmo na 103 nie blokuje: klik 5 pól", s.kliki() == [(105, 50)], s.kliki())
# 3m nauczona dziura na 104
s, b = nowy((100, 50, Z))
b.wpadniecie.dziury = {(104, 50, Z)}
marsz(b)
sprawdz("3m nauczona dziura na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3n drzwi na 104
s, b = nowy((100, 50, Z))
b.drzwi_def = [{"pole": (104, 50, Z), "id": "d", "strony": []}]
marsz(b)
sprawdz("3n drzwi na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3o ściana nauczona (krok się nie udał)
s, b = nowy((100, 50, Z))
b.sciany[(104, 50, Z)] = 0.0
marsz(b)
sprawdz("3o ściana nauczona na 104: klik do 103", s.kliki() == [(103, 50)], s.kliki())
# 3p tylko 1 bezpieczne pole przed przeszkodą: bez kliku
s, b = nowy((100, 50, Z))
b.ogien_pola = {(102, 50, Z): 1}
r = marsz(b)
sprawdz("3p przeszkoda na 102: 1 pole = za mało, bez kliku", r is None and not s.kliki(), (r, s.kliki()))
# 3q droga z kilku punktów A* (prowadz) zamiast punktów odcinka: ten sam wynik
s, b = nowy((100, 50, Z))
poz = b.postac.pozycja()
r = b._marsz_klik(poz, [(101, 50, Z), (102, 50, Z), (103, 50, Z), (103, 51, Z), (103, 52, Z)])
sprawdz("3q droga A* (prowadz) ze skrętem: klik 5 pól na (103,52)", r is True and s.kliki() == [(103, 52)], (r, s.kliki()))
# 3r pole poza widokiem ucina odcinek (±6/±4)
s, b = nowy((100, 50, Z), [(100, 50 + i, Z) for i in range(1, 12)])
cavebot.MARSZ_KLIK_MAKS_POL = 7
marsz(b)
sprawdz("3r odcinek pionowy ucięty widokiem (|dy| <= 4): klik do (100,54)", s.kliki() == [(100, 54)], s.kliki())
cavebot.MARSZ_KLIK_MAKS_POL = 5
# 3s inne piętro w odcinku
s, b = nowy((100, 50, Z), [(101, 50, Z), (102, 50, Z), (103, 50, Z + 1), (104, 50, Z + 1)])
marsz(b)
sprawdz("3s odcinek zmienia piętro: klik tylko do ostatniego pola na tym piętrze", s.kliki() == [(102, 50)], s.kliki())

# ---------- 4. obserwacja: dojście, brak ruchu, zmiana piętra ----------
# 4a idzie: drugi obieg nie klika (czeka), po dojściu planuje następny
s, b = nowy((100, 50, Z), [(100 + i, 50, Z) for i in range(1, 13)])
LOGI.clear()
marsz(b)
n0 = len(s.kliki())
r = marsz(b)
sprawdz("4a w trakcie marszu kolejny obieg czeka (True), bez nowego kliku", r is True and len(s.kliki()) == n0, s.kliki())
for _ in range(40):
    marsz(b)
    if tuple(s.poz[:2]) == (105, 50):
        marsz(b)                      # obieg, w którym marsz widzi dojście
        break
sprawdz("4b doszedł na (105,50), log 'doszedł', zaplanowany kolejny klik (110,50)",
        any("[MARSZ] doszedł na (105, 50)" in l for l in LOGI) and (110, 50) in s.kliki(), (LOGI, s.kliki()))

# 4c brak ruchu: klient nie idzie -> blokada, kroki klawiszem
s, b = nowy((100, 50, Z))
s.stoi = True
LOGI.clear()
marsz(b)
sprawdz("4c klik wysłany", s.kliki() == [(105, 50)])
for _ in range(30):
    marsz(b)
    if b.marsz_blok:
        break
sprawdz("4d brak ruchu > MARSZ_BEZ_RUCHU_S: blokada odcinka i log 'brak ruchu'", b.marsz_blok is not None
        and any("[MARSZ] brak ruchu" in l for l in LOGI), (b.marsz_blok, LOGI))
sprawdz("4e po braku ruchu marsz wyczyszczony, klik_cel zdjęty", b.marsz is None and b.klik_cel is None)
s.stoi = False
liczba, kl0, x0 = len(s.kliki()), len(s.klawisze()), s.poz[0]
for _ in range(3 - (x0 - 100)):
    marsz(b)
sprawdz("4f w blokadzie (promień MARSZ_BLOK_R): kroki klawiszem (Right), bez nowych kliknięć", len(s.kliki()) == liczba
        and set(s.klawisze()) == {"Right"} and s.poz[0] == 103, (s.klawisze(), s.kliki(), s.poz))
s.t += cavebot.MARSZ_BLOK_S + 1
marsz(b)
marsz(b) if len(s.kliki()) == liczba else None
sprawdz("4g po MARSZ_BLOK_S blokada wygasa i znów klikamy", len(s.kliki()) == liczba + 1 and b.marsz_blok is None, (len(s.kliki()), liczba))

# 4h blokada działa tylko w pobliżu miejsca zawodu
s, b = nowy((100, 50, Z))
b.marsz_blok = ((100, 50), s.t + 100)
s.poz[0] = 120
b.punkty = [(120 + i, 50, Z) for i in range(1, 21)] + [(140, 50, Z)] * 10
b.idx = 0
marsz(b)
sprawdz("4h daleko od miejsca zawodu blokada nie obowiązuje: klik", s.kliki() == [(125, 50)] and b.marsz_blok is None, (s.kliki(), b.marsz_blok))

# 4i zmiana piętra w trakcie marszu -> przerwanie i oddanie sterowania
s, b = nowy((100, 50, Z))
LOGI.clear()
marsz(b)
s.teleport = (s.t + 0.3, (102, 50, Z + 1))
for _ in range(10):
    r = marsz(b)
    if b.marsz is None:
        break
sprawdz("4i zmiana piętra: marsz przerwany, hak oddaje sterowanie (None), log o piętrze, bez Escape",
        b.marsz is None and r is None and any("zmiana piętra" in l for l in LOGI) and "Escape" not in s.klawisze(),
        (b.marsz, r, LOGI, s.klawisze()))

# 4j limit czasu: klient idzie, ale wolno (krok 0,9 s)
s, b = nowy((100, 50, Z))
s.krok_t = 0.9
LOGI.clear()
marsz(b)
for _ in range(60):
    marsz(b)
    if any("[MARSZ] limit czasu" in l or "[MARSZ] stanął" in l for l in LOGI):
        break
sprawdz("4j zbyt wolny marsz kończy się po limicie (log), bez blokady (poszliśmy)", any("[MARSZ] limit czasu" in l for l in LOGI)
        and b.marsz_blok is None and s.poz[0] > 100, (LOGI, s.poz))

# 4k klient stanął po drodze (przeszkoda, której nie znaliśmy): koniec marszu, kolejny klik od nowej pozycji
s, b = nowy((100, 50, Z))
s.blok = {(103, 50)}
LOGI.clear()
marsz(b)
for _ in range(30):
    marsz(b)
    if any("[MARSZ] stanął" in l for l in LOGI):
        break
sprawdz("4k klient stanął przed przeszkodą: log 'stanął', blokada nie (ruszyliśmy)", any("[MARSZ] stanął w (102, 50)" in l for l in LOGI)
        and b.marsz_blok is None, (LOGI, b.marsz_blok))

# ---------- 5. walka nie startuje marszu i przerywa trwający ----------
# 5a cel do walki w widoku: bez kliku
s, b = nowy((100, 50, Z))
s.stwory = [{"id": 20, "nazwa": "Troll", "gracz": False, "x": 106, "y": 50, "z": Z, "hp": 100}]
r = marsz(b)
sprawdz("5a potwór (cel do walki) w widoku: marsz nie startuje", r is None and not s.kliki() and b.marsz is None, (r, s.kliki()))
# 5b ignorowany potwór nie jest celem: marsz dozwolony
s, b = nowy((100, 50, Z))
s.stwory = [{"id": 20, "nazwa": "Troll", "gracz": False, "x": 106, "y": 50, "z": Z, "hp": 100}]
b.ignorowane[20] = s.t + 1000
r = marsz(b)
sprawdz("5b ignorowany potwór nie blokuje marszu", r is True and s.kliki() == [(105, 50)], (r, s.kliki()))
# 5c potwór pojawia się w trakcie marszu: Escape i oddanie sterowania
s, b = nowy((100, 50, Z))
LOGI.clear()
marsz(b)
marsz(b)
s.stwory = [{"id": 21, "nazwa": "Troll", "gracz": False, "x": 108, "y": 50, "z": Z, "hp": 100}]
r = marsz(b)
sprawdz("5c cel do walki w trakcie marszu: Escape, marsz wyczyszczony, hak oddaje sterowanie",
        r is None and b.marsz is None and s.klawisze() == ["Escape"] and s.cel is None
        and any("[MARSZ] przerwany (cel do walki w widoku)" in l for l in LOGI), (r, s.klawisze(), LOGI))
# 5d w dojściu (DOJSCIE_BIEGNIJ) potwór nie przerywa marszu
s, b = nowy((100, 50, Z))
b.__dict__["_w_segmencie"] = False
b2 = cavebot.CavebotDojscie(P(s), [(100 + i, 50, Z) for i in range(1, 21)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                            spij=s.spij, zegar=s.zegar, loot=None, mapa=Mapa(), klik=s.klik, czas_s=10 ** 7)
b2.wpadniecie = SimpleNamespace(dziury=set(), lista=lambda *a, **k: [], obserwuj=lambda *a: None, tick=lambda *a: None)
b2.drzwi_def = []
s.stwory = [{"id": 22, "nazwa": "Troll", "gracz": False, "x": 106, "y": 50, "z": Z, "hp": 100}]
r = b2._marsz_klik(b2.postac.pozycja(), None)
sprawdz("5d dojście: potwór w widoku nie wstrzymuje marszu (bieg bez walki)", r is True and s.kliki() == [(105, 50)], (r, s.kliki()))

# 5e walcz() zatrzymuje marsz klienta PRZED atakiem (Escape poprzedza atak)
s, b = nowy((100, 50, Z))
marsz(b)
marsz(b)
s.poz[0] = 103                       # klient idzie dalej; potwór podchodzi
s.stwory = [{"id": 30, "nazwa": "Rat", "gracz": False, "x": 104, "y": 50, "z": Z, "hp": 100}]
b.stan = "WALKA"
LOGI.clear()
for _ in range(6):
    b.tick()
    if any(e[0] == "atak" for e in s.ev):
        break
kol = [e for e in s.ev if e[0] in ("atak",) or e == ("klawisz", "Escape")]
sprawdz("5e walka: Escape (stop marszu) poprzedza pierwszy atak, marsz wyczyszczony",
        kol and kol[0] == ("klawisz", "Escape") and any(e[0] == "atak" for e in kol) and b.marsz is None, (kol, b.marsz, LOGI[-5:]))
# 5f zatrzymaj_klik() (ucieczka, PK, ogień) też kończy marsz Escape
s, b = nowy((100, 50, Z))
marsz(b)
marsz(b)
w = b.zatrzymaj_klik(b.postac.pozycja())
sprawdz("5f zatrzymaj_klik w trakcie marszu: Escape, marsz wyczyszczony", w is True and b.marsz is None and s.klawisze() == ["Escape"],
        (w, s.klawisze()))
# 5g po dojściu zatrzymaj_klik nie wysyła zbędnego Escape
s, b = nowy((100, 50, Z))
marsz(b)
for _ in range(20):
    marsz(b)
    if tuple(s.poz[:2]) == (105, 50):
        break
marsz(b)                              # obserwacja dojścia
b.marsz = None
sprawdz("5g po dojściu nie ma Escape", "Escape" not in s.klawisze())
# 5h gracz w zasięgu unikania/mijania: bez marszu, klawisze zostają
s, b = nowy((100, 50, Z))
b.unikanie = SimpleNamespace(gracze=[{"nazwa": "Obcy"}], duchy=[], mijanie_trzyma=lambda: False)
r = marsz(b)
sprawdz("5h gracz w zasięgu unikania: bez marszu klikiem", r is None and not s.kliki() and b.marsz is None, (r, s.kliki()))
cavebot.MIJANIE = 1
b.unikanie = SimpleNamespace(gracze=[], duchy=[], mijanie_trzyma=lambda: True)
r = marsz(b)
cavebot.MIJANIE = 0
sprawdz("5i MIJANIE=1 i mijanie trzyma decyzję: bez marszu klikiem", r is None and not s.kliki(), (r, s.kliki()))
# 5j gracz pojawia się w trakcie marszu: Escape
s, b = nowy((100, 50, Z))
marsz(b)
marsz(b)
b.unikanie = SimpleNamespace(gracze=[{"nazwa": "Obcy"}], duchy=[], mijanie_trzyma=lambda: False)
r = marsz(b)
sprawdz("5j gracz w zasięgu w trakcie marszu: Escape i oddanie sterowania", r is None and b.marsz is None and s.klawisze() == ["Escape"],
        (r, s.klawisze()))
# 5k pole na drodze zajęte w trakcie marszu: Escape i nowy plan krótszym odcinkiem
s, b = nowy((100, 50, Z))
marsz(b)
marsz(b)
s.stwory = [{"id": 40, "nazwa": "Obcy", "gracz": True, "x": 105, "y": 50, "z": Z, "hp": 100}]
b.potwory = {"nigdy"}
r = marsz(b)
sprawdz("5k stwór wszedł na pole docelowe: Escape i nowy klik krótszy (do 104)", "Escape" in s.klawisze() and s.kliki()[-1] == (104, 50),
        (s.klawisze(), s.kliki()))
# 5l marsz porzucony (obiegi poszły gdzie indziej) wygasa bez Escape
s, b = nowy((100, 50, Z))
marsz(b)
s.t += cavebot.MARSZ_PORZUCONY_S + 1
s.poz[0] = 103
b.idx = 0
b.marsz["hook"] = s.t - cavebot.MARSZ_PORZUCONY_S - 0.5
b.punkty = [(103 + i, 50, Z) for i in range(1, 21)] + [(123, 50, Z)] * 10
s.cel = None
marsz(b)
sprawdz("5l porzucony marsz nie daje Escape i jest zastąpiony nowym klikiem", "Escape" not in s.klawisze() and s.kliki()[-1] == (108, 50),
        (s.klawisze(), s.kliki()))

# ---------- 6. pełny obieg przez _idz_segment (patrol) ----------
LOGI.clear()
random.seed(2)
s, b = nowy((100, 50, Z))
seg = [(100 + i, 50, Z) for i in range(1, 26)]
idx = 0
for _ in range(200):
    _w, idx = b._idz_segment(seg, idx)       # idx odcinka trzyma patrol (p["idx"]) między obiegami
    if tuple(s.poz[:2]) == (125, 50):
        break
sprawdz("6a _idz_segment przy MARSZ_KLIK=1: dochodzi do końca odcinka, linie [MARSZ] w logu, mało klawiszy",
        tuple(s.poz[:2]) == (125, 50) and any("[MARSZ] klik na" in l for l in LOGI) and len(s.klawisze()) <= 2,
        (s.poz, len(s.kliki()), s.klawisze()))

cavebot.MARSZ_KLIK = 0
print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
