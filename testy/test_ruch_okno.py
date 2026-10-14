"""R0b: ruch_okno i próbka przed wczesnym return True w Cavebot.tick (integracja na atrapach, RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, tempfile
sys.dont_write_bytecode = True
_katalog = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _katalog)
from pathlib import Path
import cavebot, bot, pokretla, telemetria
import mapa as _mapa_mod

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
cavebot.OGIEN_UNIKAJ = 1

LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))

class AtrapaMapy(_mapa_mod.Mapa):
    def __init__(s, wolne, z=7):
        s._dane, s._spis, s._bloki, s.wersja = b"", {}, {}, 1
        pola_ = {tuple(p[:2]): 1 for p in wolne}
        for bx, by in {(x >> 6, y >> 6) for x, y in pola_}:
            b = bytearray(bytes([5, 114, 0]) * 4096)
            for (x, y), f in pola_.items():
                if (x >> 6, y >> 6) == (bx, by):
                    b[((y & 63) * 64 + (x & 63)) * 3] = f
            s._bloki[_mapa_mod._klucz_bloku(bx << 6, by << 6, z)] = bytes(b)

class Swiat:
    def __init__(s, wolne, poz=(100, 100, 7)):
        s.t = 0.0; s.poz = list(poz); s.stwory = []; s.klawisze = []; s.kroki = []; s.kliki = []
        s.wolne = set(wolne); s.hp = 190; s.zbierz = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        s = p.s; d = bot.KIERUNKI[k]; s.t += 0.2
        n = (s.poz[0] + d[0], s.poz[1] + d[1])
        s.kroki.append((k, n))
        if n not in s.wolne or any((m["x"], m["y"]) == n for m in s.stwory):
            return None
        s.poz[0], s.poz[1] = n
        return tuple(s.poz)

def pas(x0=90, x1=120, y0=100, y1=100): return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

def zrob(s, punkty=None, klik=False, **kw):
    loot = types.SimpleNamespace(zbierz=lambda z, g: (s.zbierz.append(tuple(z)), "ok")[1], zjedz=lambda log=None: [],
                                 ile_jedzenia=lambda: None)
    punkty = punkty or [(100 + i, 100, 7) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=kw.pop("okrazenia", 1), jedzenie="F5",
                        mapa=AtrapaMapy(s.wolne), klik=(lambda dx, dy: s.kliki.append((dx, dy))) if klik else None, **kw)
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def ogien_w(b, s, *pola_):
    for p in pola_:
        b.ogien_pola[(p[0], p[1], 7)] = s.t

def z_tele(s, **kw):
    b = zrob(s, **kw)
    b.tele = telemetria.Telemetria(Path(tempfile.mkdtemp()), zegar=s.zegar, zapis=False)
    return b

sprawdz("1a domyślnie włączone", cavebot.RUCH_OKNO == 1 and cavebot.RUCH_PROBKA_WCZESNA == 1)
sprawdz("1b ZAKRESY i KIERUNEK", pokretla.ZAKRESY.get("RUCH_OKNO") == (0, 1) and pokretla.ZAKRESY.get("RUCH_PROBKA_WCZESNA") == (0, 1)
        and pokretla.waliduj({"RUCH_OKNO": 0}, {"RUCH_OKNO": 1})[0] == {})

# 2. ruch_okno z zwykłych obiegów
s = Swiat(pas(90, 140, 100, 100)); b = z_tele(s, klik=True, okrazenia=None, punkty=[(135 + i, 100, 7) for i in range(5)])
for i in range(120):
    b.tick(); s.t += 0.4
    if i % 3: s.poz[0] = 95 + i // 3 % 15      # postać idzie sama po kliku (atrapa klika nie przesuwa)
okna = [r for r in b.tele.rek if r["typ"] == "ruch_okno"]
sprawdz("2a rekord ruch_okno powstaje", len(okna) >= 1, f"{len(okna)}")
sprawdz("2b okno ok. 30 s, ticki liczone", okna and 29 <= okna[0]["okno_s"] <= 40 and okna[0]["ticki"] > 10, okna[:1])
sprawdz("2c kliki policzone (klik w mapę)", okna and okna[0]["kliki"] >= 1, okna[:1])

# 3. pokrętło wyłącza
cavebot.RUCH_OKNO = 0
s = Swiat(pas(90, 140, 100, 100)); b = z_tele(s, klik=True, okrazenia=None, punkty=[(135 + i, 100, 7) for i in range(5)])
for _ in range(120):
    b.tick(); s.t += 0.4
sprawdz("3a RUCH_OKNO=0: brak rekordów", not [r for r in b.tele.rek if r["typ"] == "ruch_okno"])
cavebot.RUCH_OKNO = 1

# 4. przyczyny stania
s = Swiat(pas(90, 140, 100, 100)); b = z_tele(s)
b.stan = "IDZ"
sprawdz("4a inne", b._ruch_powod((100, 100, 7), s.t) == "inne")
b.ruch_pietra_t = s.t - 0.5
sprawdz("4b schody", b._ruch_powod((100, 100, 7), s.t) == "schody")
b.ruch_pietra_t = float("-inf"); b.ogien_krok_t = s.t - 1.0
sprawdz("4c ogień", b._ruch_powod((100, 100, 7), s.t) == "ogien")
b.ogien_krok_t = float("-inf"); b.patrol = {"faza": "postoj"}
sprawdz("4d postój patrolu", b._ruch_powod((100, 100, 7), s.t) == "patrol_postoj")
b.patrol = None; b.stan = "LOOT"
sprawdz("4e loot", b._ruch_powod((100, 100, 7), s.t) == "loot")
b.stan = "WALKA"
sprawdz("4f walka", b._ruch_powod((100, 100, 7), s.t) == "walka")
b.stan = "IDZ"; b.tele.utknieto = True
sprawdz("4g utknięcie", b._ruch_powod((100, 100, 7), s.t) == "utkniecie")

# 5. próbka przed wczesnym return True (stoimy na ogniu: _ogien_wyjdz kończy obieg)
s = Swiat(pas(95, 110, 100, 100)); b = z_tele(s)
b.tick()                       # zwykły obieg: pierwsza próbka
s.t += 2.0
ogien_w(b, s, (100, 100), (101, 100))
b.tick()
wcz = [r for r in b.tele.rek if r["typ"] == "probka" and r.get("wczesna")]
sprawdz("5a wczesne zakończenie obiegu (ogień) zostawia próbkę z polem wczesna", len(wcz) == 1 and wcz[0]["wczesna"] == "ogien_wyjdz", wcz)
cavebot.RUCH_PROBKA_WCZESNA = 0
s.t += 2.0
ogien_w(b, s, (99, 100), (98, 100))
b.postac.s.poz[0] = 99
b.tick()
sprawdz("5b RUCH_PROBKA_WCZESNA=0: bez nowej próbki wczesnej", len([r for r in b.tele.rek if r.get("wczesna")]) == 1)
cavebot.RUCH_PROBKA_WCZESNA = 1

# 6. wyjątek w telemetrii nie wywraca obiegu
s = Swiat(pas(90, 140, 100, 100)); b = z_tele(s, klik=True, okrazenia=None, punkty=[(135 + i, 100, 7) for i in range(5)])
def zle(*a, **k): raise RuntimeError("x")
b.tele.ruch_tick = zle; b.tele.probka = zle
try:
    for _ in range(5):
        b.tick(); s.t += 0.4
    sprawdz("6a błąd ruch_tick/probka nie wywraca tick", True)
except Exception as e:
    sprawdz("6a błąd ruch_tick/probka nie wywraca tick", False, repr(e))

print("WYNIK:", "OK" if all(ok) else "BŁĄD")
sys.exit(0 if all(ok) else 1)
