"""23.10 dziura (32467,32233,z7) w jaskini trolli Thais (wydra wpadła dwa razy: 07:53:40 i 11:08:51 w drodze z depo Thais,
w dojściu/wyprawie, czyli przy wypad_aktywny=True, gdy zakaz zmiany piętra z mapy jest wyłączony). Lądowanie (32467,32233,z8)
w grupie trzech trolli. Pole musi być w `trasy/dziury_omijaj.json` (ręczna lista, wczytywana przez wpadniecie.py razem z
nauczonymi) i być ścianą dla WSZYSTKICH ścieżek ruchu: A*, krok_do, pościg, kliki marszu (patrol i wypad). Trasy nadal przechodzą.
Atrapa klienta z prawdziwą mapą serwera (mapa.py) i trasami z `trasy/`; bez gry, bez gniazd, bez zapisów w danych."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie, wypad
from pathlib import Path

cavebot.log = lambda *a: None
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, "" if warunek else f" [{info}]")

M = _mapa.Mapa()
DZIURA = (32467, 32233, 7)
LADOWANIE = (32467, 32233, 8)
OMIJAJ = Path(_R) / "trasy" / "dziury_omijaj.json"
TRASY = Path(_R) / "trasy"

# --- 0. dowód z mapy klienta: jedyne pole z flagą 2 w promieniu 6, kolor 210 pod spodem, sąsiedzi zwykli
f = M.pole(*DZIURA)
sprawdz("0a mapa: pole (32467,32233,z7) ma flagę 2 (chodliwe + BEZ_DROGI), bez ściany", f and f[0] == 3, f)
sprawdz("0b mapa: pod spodem (32467,32233,z8) żółte pole 210 (zmiana piętra), chodliwe", M.pole(*LADOWANIE) == (1, 210, 14), M.pole(*LADOWANIE))
inne = [(x, y) for x in range(DZIURA[0] - 6, DZIURA[0] + 7) for y in range(DZIURA[1] - 6, DZIURA[1] + 7)
        if (x, y) != DZIURA[:2] and M.flagi(x, y, 7) & 2]
sprawdz("0c mapa: w promieniu 6 na z7 nie ma innego pola z flagą 2", not inne, inne)
sprawdz("0d mapa: pola z logu (32467,32232,z7) i (32466,32230,z7) zwykłe (flaga 1), po nich bot chodził bez upadku",
        M.flagi(32467, 32232, 7) == 1 and M.flagi(32466, 32230, 7) == 1)

# --- 1. źródło prawdy: plik ręczny + nauczone, bez mieszania przy zapisie
def wczytaj_plik(p):
    d = json.loads(Path(p).read_text())
    return {tuple(e) for e in (d["dziury"] if isinstance(d, dict) else d)}
sprawdz("1a trasy/dziury_omijaj.json istnieje i zawiera pole", OMIJAJ.exists() and DZIURA in wczytaj_plik(OMIJAJ), OMIJAJ.exists())
kat = Path(tempfile.mkdtemp())
try:
    w = wpadniecie.Wpadniecie(types.SimpleNamespace(), plik=kat / "n.json", plik_omijaj=OMIJAJ, log=lambda *a: None)
    sprawdz("1b Wpadniecie wczytuje pole z pliku ręcznego", DZIURA in w.dziury, sorted(w.dziury)[:3])
    w.ucz((1, 2, 3))
    zapis = wczytaj_plik(kat / "n.json")
    sprawdz("1c zapis nauczonych NIE przepisuje wpisów ręcznych (bot na żywo nie skasuje ich przy nauce)",
            (1, 2, 3) in zapis and DZIURA not in zapis, sorted(zapis))
    w2 = wpadniecie.Wpadniecie(types.SimpleNamespace(), plik=kat / "n.json", plik_omijaj=OMIJAJ, log=lambda *a: None)
    sprawdz("1d po ponownym wczytaniu: nauczone + ręczne", {(1, 2, 3), DZIURA} <= w2.dziury)
    w3 = wpadniecie.Wpadniecie(types.SimpleNamespace(), plik=kat / "n.json", plik_omijaj=kat / "brak.json", log=lambda *a: None)
    sprawdz("1e brak pliku ręcznego = tylko nauczone, bez błędu", w3.dziury == {(1, 2, 3)}, w3.dziury)
except TypeError as e:
    sprawdz("1b Wpadniecie przyjmuje plik_omijaj", False, repr(e))

# --- 2. trasy: nic nie używa tego pola jako przejścia ani punktu, a odcinki z7 nadal mają drogę z ścianą w tym polu
def punkty(p):
    d = json.loads(p.read_text())
    return d if isinstance(d, list) else (d.get("punkty") or d.get("trasa") or [])
uzycia, zmiana = [], []
for p in sorted(TRASY.glob("*.json")):
    try:
        pk = [tuple(q[:3]) for q in punkty(p) if isinstance(q, (list, tuple)) and len(q) > 2]
    except Exception:
        continue
    for i, q in enumerate(pk):
        if q == DZIURA:
            uzycia.append((p.name, i))
        if i and pk[i - 1][:2] == DZIURA[:2] and pk[i - 1][2] == 7 and q[2] != 7:
            zmiana.append((p.name, i))
sprawdz("2a żadna trasa nie ma tego pola jako punktu ani przejścia pięter (wyjątek od ściany niepotrzebny)", not uzycia and not zmiana, (uzycia, zmiana))


class Swiat:
    """Atrapa klienta z trzymanym klawiszem na prawdziwej mapie. Wejście na DZIURA = upadek na z8. KROK s, bez opóźnienia startu."""
    KROK = 0.45
    def __init__(s, poz):
        s.t = 0.0; s.poz = list(poz); s.trzym = None; s.krok = None; s.upadki = []; s.nielegalne = 0; s.stwory = []
        s.troll = [poz[0], poz[1] + 4, poz[2]]; s.dziura_xy = {DZIURA[:2]}; s.kroki = []
    def zegar(s): return s.t
    def idzie(s, x, y, z):
        v = M.flagi(x, y, z); return bool(v & 1) and not v & 4
    def _wejdz(s, v):
        x, y = s.poz[0] + v[0], s.poz[1] + v[1]
        if not s.idzie(x, y, s.poz[2]):
            s.nielegalne += 1; return False
        if s.poz[2] == 7 and (x, y) in s.dziura_xy:
            s.upadki.append((tuple(s.poz), (x, y, 8), round(s.t, 2)))
            s.poz[:] = [x, y, 8]; return True
        s.poz[0], s.poz[1] = x, y; s.kroki.append((x, y, s.poz[2])); return True
    def advance(s):
        while s.krok is not None and s.t >= s.krok[0]:
            v = s.krok[1]; s.krok = None
            if not s._wejdz(v): return
            if s.trzym is not None and s.poz[2] == 7:
                s.krok = (s.t + s.KROK, s.trzym)
        if s.krok is None and s.trzym is not None and s.poz[2] == 7:
            s.krok = (s.t + s.KROK, s.trzym)
    def spij(s, d): s.t += d; s.advance()
    def pozycja(s): s.t += 0.035; s.advance(); return tuple(s.poz)
    def trzymaj_kierunek(s, dx, dy):
        s.advance(); s.trzym = (dx, dy); s.advance()
    def puszczaj(s): s.advance(); s.trzym = None
    def krok_k(s, k):
        d = bot.KIERUNKI[k]; s.t += s.KROK
        return s._wejdz(d)
    def zapytaj(s, z):
        s.t += 0.04; s.advance()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        troll = {"id": 7, "nazwa": "Troll", "gracz": False, "x": s.troll[0], "y": s.troll[1], "z": s.troll[2], "hp": 80}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}, dict(troll)]}
        if z["cmd"] == "poscig":
            return {"pozycja": {"x": s.poz[0], "y": s.poz[1], "z": s.poz[2]},
                    "stwor": {**{k: troll[k] for k in ("id", "x", "y", "z", "hp")}, "atakowany": True, "bije_nas": False}}
        if z["cmd"] == "stwor":
            return {"stwor": {**{k: troll[k] for k in ("id", "x", "y", "z", "hp")}, "atakowany": True, "bije_nas": False}}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return p.s.pozycja()
    def trzymaj_kierunek(p, dx, dy): p.s.trzymaj_kierunek(dx, dy)
    def puszczaj(p): p.s.puszczaj()
    def trzymany_kierunek(p): return p.s.trzym
    def puls(p): pass
    def klawisz(p, k): pass
    def krok(p, k): return p.s.krok_k(k)
    def krok_skos(p, dx, dy):
        p.s.t += p.s.KROK
        return tuple(p.s.poz) if p.s._wejdz((dx, dy)) else None


def nowy(start, wypad_aktywny, trasa=None):
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"            # nauczone: pusty plik tymczasowy
    wpadniecie.PLIK_DZIUR_OMIJAJ = OMIJAJ                           # ręczna lista: prawdziwy plik z danych
    s = Swiat(start)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    kliki = []
    b = cavebot.Cavebot(P(s), trasa or [start], zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=lambda dx, dy: kliki.append((dx, dy)))
    b.spij = s.spij
    class Tele:
        def zdarzenie(self, typ, **d): pass
        def probka(self, *a): return None
        def linia(self, *a): pass
    class Pokr:
        def odswiez(self): pass
    b.tele = Tele(); b.pokretla = Pokr(); b.pokretla_ost = float("-inf")
    b.czy_atakowany = lambda stwor, gracz: True
    b.wypad_aktywny = wypad_aktywny
    b._wp().plik_stop = kat / "STOP"
    s.kliki = kliki
    return s, b


# --- 3. Cavebot widzi pole jako ścianę (także w wypadzie/wyprawie, gdzie zakaz z mapy jest wyłączony)
for wa in (False, True):
    s, b = nowy((32467, 32231, 7), wa)
    sprawdz(f"3a wypad={wa}: dziura_nauczona i pole_zmiany_pietra dla pola; sąsiedzi nie",
            b.dziura_nauczona(DZIURA) and b.pole_zmiany_pietra(DZIURA)
            and not b.dziura_nauczona((32467, 32232, 7)) and not b.pole_zmiany_pietra((32468, 32233, 7)))
    d = b.droga((32467, 32232, 7), (32467, 32234), dlugosc=0)
    sprawdz(f"3b wypad={wa}: A* z (32467,32232) do (32467,32234) omija pole i droga istnieje",
            d is not None and DZIURA[:2] not in [tuple(q[:2]) for q in d], d)
    d = b.droga((32466, 32230, 7), (32469, 32234), dlugosc=0)
    sprawdz(f"3c wypad={wa}: A* z (32466,32230) do (32469,32234) bez pola", d is not None and DZIURA[:2] not in [tuple(q[:2]) for q in d], d)

# --- 4. krok_do (dojście, wyprawa, omijanie): cel za dziurą w linii prostej, mob blokuje obejście z jednej strony
for wa in (False, True):
    s, b = nowy((32467, 32232, 7), wa)
    for _ in range(12):
        poz = tuple(s.poz)
        if poz[:2] == (32467, 32234) or poz[2] != 7:
            break
        b.krok_do((32467, 32234, 7))
    sprawdz(f"4a wypad={wa}: krok_do do (32467,32234) nie wchodzi w dziurę", not s.upadki and s.poz[2] == 7, (s.upadki, s.poz))
    # jak _idz_trasa: A* do celu, krok_do na kolejne pola drogi; trasa przez okolicę dziury dochodzi do celu
    s, b = nowy((32467, 32232, 7), wa)
    for q in b.droga((32467, 32232, 7), (32467, 32235), dlugosc=0) or []:
        for _ in range(3):
            if tuple(s.poz[:2]) == tuple(q[:2]):
                break
            b.krok_do((q[0], q[1], 7))
    sprawdz(f"4b wypad={wa}: A* + krok_do dochodzą do (32467,32235) za dziurą", tuple(s.poz) == (32467, 32235, 7) and not s.upadki, (s.poz, s.upadki))
    # kierunek bezpośrednio na dziurę ze skosu: cel (32468,32234) z (32466,32232) -> skos przez (32467,32233)
    s, b = nowy((32466, 32232, 7), wa)
    for _ in range(12):
        if tuple(s.poz[:2]) == (32468, 32234) or s.poz[2] != 7:
            break
        b.krok_do((32468, 32234, 7))
    sprawdz(f"4c wypad={wa}: skos (32466,32232)->(32468,32234) nie przechodzi przez dziurę", not s.upadki and s.poz[2] == 7, (s.upadki, s.poz))

# --- 5. pościg (trzymany klawisz) za Trollem stojącym za dziurą: mapa w wypadzie pozwala, nauczona/ręczna lista zabrania
for wa in (False, True):
    s, b = nowy((32467, 31, 7) if False else (32467, 32231, 7), wa)
    s.troll[:] = [32467, 32235, 7]
    b.postac.pozycja()
    b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
    g = {"hp": 100, "max_hp": 100, "proc": 100.0}
    cel = {"id": 7, "nazwa": "Troll", "gracz": False, "x": 32467, "y": 32235, "z": 7, "hp": 80, "adres": "0x1000"}
    b.poscig_szybki(cel, tuple(s.poz), g)
    sprawdz(f"5 wypad={wa}: pościg za Trollem za dziurą nie kończy się upadkiem", not s.upadki and s.poz[2] == 7, (s.upadki, s.poz))

# --- 6. kliki marszu: patrol/dojście (Cavebot._marsz_klik) i wypad (Wypad._klik_dziury) nie prowadzą klienta przez pole
cavebot.MARSZ_KLIK = 1
try:
    for wa in (False,):
        seg = [(32464, 32230, 7), (32465, 32230, 7), (32466, 32231, 7), (32467, 32232, 7), (32467, 32233, 7), (32467, 32234, 7), (32467, 32235, 7),
               (32467, 32236, 7)]
        s, b = nowy((32465, 32229, 7), wa, trasa=seg)
        b.punkty = [tuple(p) for p in seg] + [tuple(seg[-1])] * 10
        b.idx = 0; b.otwarta = True; b.stan = "IDZ"; b.__dict__["_w_segmencie"] = True
        b.zajete_xy = lambda *a, **k: set()
        try:
            r = b._marsz_klik(tuple(s.poz), None)
        except Exception as e:
            r = repr(e)
        kl = [(32465 + dx, 32229 + dy) for dx, dy in s.kliki]
        bad = [c for c in kl if min(c[0], 32465) - 1 <= DZIURA[0] <= max(c[0], 32465) + 1 and min(c[1], 32229) - 1 <= DZIURA[1] <= max(c[1], 32229) + 1]
        sprawdz("6a marsz klikiem po odcinku przez dziurę nie klika celu, którego prostokąt obejmuje pole", not bad, (r, kl))
    w = types.SimpleNamespace(cb=b)
    wz = wypad.Wypad._klik_dziury(w, (32466, 32231, 7), [(32467, 32232), (32468, 32233)])
    sprawdz("6b wypad: _klik_dziury widzi pole w prostokącie postać+ścieżka (margines 1)", DZIURA[:2] in wz, wz)
finally:
    cavebot.MARSZ_KLIK = 0

# --- 7. trasy nadal przechodzą: wszystkie odcinki z7 depo_troll_cave i troll_z_miasta mają drogę A* przy ścianie w polu
for nazwa in ("depo_troll_cave", "troll_z_miasta"):
    pk = [tuple(q[:3]) for q in punkty(TRASY / f"{nazwa}.json")]
    s, b = nowy(pk[0], True)
    zle = []
    for a, c in zip(pk, pk[1:]):
        if a[2] != 7 or c[2] != 7 or a[:2] == c[:2] or max(abs(a[0] - 32467), abs(a[1] - 32233)) > 8:
            continue
        d = b.droga(a, c[:2], dlugosc=0)
        if d is None or DZIURA[:2] in [tuple(q[:2]) for q in d]:
            zle.append((a, c, None if d is None else len(d)))
    sprawdz(f"7 {nazwa}: odcinki w okolicy dziury (<=8 pól) mają drogę i omijają pole", not zle, zle)
    sprawdz(f"7 {nazwa}: żaden punkt trasy nie leży na polu", DZIURA not in pk)

# --- 8. pozostałe haki ruchu czytają to samo: omijanie graczy/mobów (unikanie, mijanie), loot, krok prosto
for wa in (False, True):
    s, b = nowy((32467, 32232, 7), wa)
    d = b._unikanie_droga((32467, 32232, 7), (32467, 32234), [])
    sprawdz(f"8a wypad={wa}: _unikanie_droga (unikanie.py) omija pole", d is not None and DZIURA[:2] not in [tuple(q[:2]) for q in d], d)
    sprawdz(f"8b wypad={wa}: _mijanie_wolne/_pole_zablokowane: pole zajęte, sąsiedzi wolni",
            not b._mijanie_wolne(DZIURA) and b._pole_zablokowane(DZIURA, ()) and b._mijanie_wolne((32467, 32232, 7))
            and b._mijanie_wolne((32466, 32233, 7)))
    sprawdz(f"8c wypad={wa}: loot/pamięć (_pamiec_pole_ok) i ogień (_ogien_przechodnie) nie uznają pola za chodliwe",
            not b._pamiec_pole_ok(DZIURA[0], DZIURA[1], DZIURA[2], set()) and not b._ogien_przechodnie(DZIURA))
    ruszylo = b.krok_prosto((32467, 32234), (32467, 32232, 7), pauza=False)
    sprawdz(f"8d wypad={wa}: krok_prosto w stronę celu za dziurą nie wpada", not s.upadki, s.upadki)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
