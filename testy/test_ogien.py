"""Pola ognia (ogien.py + integracja w cavebot.py): wykrywanie na zrzutach i omijanie ognia w drodze,
krokach, lootcie i zejście z pola ognia. Na atrapach i zapisanych zrzutach, bez X11 (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
_katalog = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _katalog)
from pathlib import Path
from PIL import Image, ImageDraw
import cavebot, bot, pokretla, ogien, ekran
import mapa as _mapa_mod

DANE = Path(_katalog) / "testy" / "dane"
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

# --- 1. wykrywanie na zrzutach -------------------------------------------------------------
R1 = (0, 195, 551, 598)      # mapa na zrzucie z1/z2 (ekran.prostokat_mapy wykrywa ją tak samo)
def pola(plik, rect=R1): return ogien.pola_ognia(Image.open(DANE / plik).convert("RGB"), rect)
ekran._cache_mapy.clear()
sprawdz("1a prostokąt mapy z1 jak R1", ekran.prostokat_mapy(Image.open(DANE / "ogien_z1.png").convert("RGB")) == R1)
sprawdz("1b zrzut kalibracyjny: dokładnie 2 pola ognia (lewo-dół i prawo-dół), pole stwora z ramką nie",
        pola("ogien_z1.png") == {(-1, 3), (6, 4)}, ogien.opis(pola("ogien_z1.png")))
sprawdz("1c ta sama scena w innej fazie animacji", pola("ogien_z2.png") == {(-1, 3), (6, 4)}, ogien.opis(pola("ogien_z2.png")))
sprawdz("1d inny zrzut z ogniem (przesunięty prostokąt)", pola("ogien_z3.png", (0, 215, 550, 617)) == {(-2, -1)},
        ogien.opis(pola("ogien_z3.png", (0, 215, 550, 617))))
for n in ("ogien_bez_atak.png", "ogien_bez_gra.png", "ogien_bez_shot.png"):
    sprawdz(f"1e brak fałszywych trafień: {n}", pola(n) == set(), ogien.opis(pola(n)))

# syntetyczne: ogień, pasek HP, ramka ataku, złoty przedmiot, krew, podłoga
def obraz():
    im = Image.new("RGB", (734, 910), (24, 24, 28))
    ImageDraw.Draw(im).rectangle(R1, fill=(110, 36, 22))        # podłoga jaskini
    return im
def pole_xy(dx, dy):
    L, T, R, B = R1; bx, by = (R - L) / 15, (B - T) / 11
    return L + (7 + dx) * bx, T + (5 + dy) * by, bx, by
syn = obraz(); d = ImageDraw.Draw(syn)
x, y, bx, by = pole_xy(2, 1)                                     # ogień: plama pomarańczowa z żółtym środkiem
d.ellipse((x + 6, y + 6, x + bx - 6, y + by - 6), fill=(240, 70, 0)); d.ellipse((x + 12, y + 12, x + bx - 12, y + by - 12), fill=(255, 130, 10))
x, y, bx, by = pole_xy(-3, -2)                                   # pasek HP: 27x4 px czerwono-pomarańczowy
d.rectangle((x + 4, y + 2, x + 30, y + 5), fill=(255, 40, 0))
x, y, bx, by = pole_xy(0, 2)                                     # ramka ataku: czysty czerwony kontur pola
d.rectangle((x + 1, y + 1, x + bx - 2, y + by - 2), outline=(255, 0, 0), width=2)
x, y, bx, by = pole_xy(4, -3)                                    # złoty przedmiot: B ~ 25, G/R ~ 0.64
d.ellipse((x + 6, y + 6, x + bx - 6, y + by - 6), fill=(220, 140, 25))
x, y, bx, by = pole_xy(-5, 2)                                    # krew: rozproszone czerwone plamki
for i in range(0, 20, 3):
    d.point((x + 5 + i, y + 8 + i % 7), fill=(200, 10, 10)); d.point((x + 6 + i, y + 9 + i % 5), fill=(220, 20, 0))
sprawdz("1f syntetyczne: tylko plama ognia", ogien.pola_ognia(syn, R1) == {(2, 1)}, ogien.opis(ogien.pola_ognia(syn, R1)))
sprawdz("1g opis", ogien.opis({(2, 1), (-1, 0)}) == "(-1,+0) (+2,+1)" and ogien.opis(set()) == "brak")

# --- 2. pokrętło ----------------------------------------------------------------------------
sprawdz("2a domyślnie włączone", cavebot.OGIEN_UNIKAJ == 1)
sprawdz("2b ZAKRESY", pokretla.ZAKRESY.get("OGIEN_UNIKAJ") == (0, 1))
sprawdz("2c Karol może wyłączyć", pokretla.waliduj({"OGIEN_UNIKAJ": 0})[0] == {"OGIEN_UNIKAJ": 0}
        and pokretla.waliduj({"OGIEN_UNIKAJ": 2})[0] == {})
sprawdz("2d analityk nie wyłączy", pokretla.waliduj({"OGIEN_UNIKAJ": 0}, {"OGIEN_UNIKAJ": 1})[0] == {})
pk = pokretla.Pokretla(cavebot, plik="/nie/ma")
sprawdz("2e Pokretla widzi OGIEN_UNIKAJ", pk.domyslne.get("OGIEN_UNIKAJ") == 1)
pk.zastosuj({"OGIEN_UNIKAJ": 0}); wyl = cavebot.OGIEN_UNIKAJ
pk.zastosuj({})
sprawdz("2f zastosuj ustawia i przywraca", wyl == 0 and cavebot.OGIEN_UNIKAJ == 1)

# --- 3. cavebot na atrapach -----------------------------------------------------------------
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
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
                        spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5",
                        mapa=AtrapaMapy(s.wolne), klik=(lambda dx, dy: s.kliki.append((dx, dy))) if klik else None, **kw)
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def ogien_w(b, s, *pola_):
    for p in pola_:
        b.ogien_pola[(p[0], p[1], 7)] = s.t

cavebot.OGIEN_UNIKAJ = 1
cavebot.OGIEN_LOG_S = 1.0     # testy 3a: wpisy co 1 s (domyślnie od P6 co 10 s, patrz test 6)

# 3a. odczyt: względne -> bezwzględne, log tylko przy zmianie
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
sprawdz("3a0 w testach bez źródła ognia (nie robi zrzutów)", b.ogien_odczyt is None)
L0 = len(LOGI)
b.ogien_odczyt = lambda: {(2, 0), (-1, 1)}
b._ogien_tick((100, 100, 7), s.t, wymus=True)
sprawdz("3a1 pola bezwzględne", set(b.ogien_pola) == {(102, 100, 7), (99, 101, 7)}, sorted(b.ogien_pola))
logi = [l for l in LOGI[L0:] if l.startswith("[OGIEN] pola:")]
sprawdz("3a2 jeden wpis [OGIEN] pola", len(logi) == 1 and "(102,100)" in logi[0] and "(99,101)" in logi[0], logi)
for _ in range(5):
    s.t += 1.0; b._ogien_tick((100, 100, 7), s.t)
sprawdz("3a3 bez spamu przy tym samym zbiorze", len([l for l in LOGI[L0:] if l.startswith("[OGIEN] pola:")]) == 1)
s.t += 0.1; b._ogien_tick((100, 100, 7), s.t)
sprawdz("3a4 odświeżenie nie częściej niż OGIEN_ODSWIEZ_S", b.ogien_t < s.t)
# znika po OGIEN_BRAK_S bez wykrycia
b.ogien_odczyt = lambda: set()
s.t += 1.0; b._ogien_tick((100, 100, 7), s.t)
sprawdz("3a5 pierwszy brak wykrycia: jeszcze pamiętamy (migotanie)", len(b.ogien_pola) == 2)
s.t += 1.0; b._ogien_tick((100, 100, 7), s.t)
sprawdz("3a6 po OGIEN_BRAK_S ogień znika i jest wpis 'brak'", not b.ogien_pola and any("[OGIEN] pola: brak" in l for l in LOGI))
# wyjątek źródła nie wywraca
def zle(): raise RuntimeError("brak gnazda")
b.ogien_odczyt = zle
s.t += 1.0; b._ogien_tick((100, 100, 7), s.t)
sprawdz("3a7 błąd odczytu: log, bez wyjątku", any("nie wykryję ognia" in l for l in LOGI))
# wyłączone pokrętłem
b.ogien_odczyt = lambda: {(1, 0)}
cavebot.OGIEN_UNIKAJ = 0
s.t += 1.0; b._ogien_tick((100, 100, 7), s.t)
sprawdz("3a8 OGIEN_UNIKAJ=0: nic nie wykrywa i droga ignoruje", not b.ogien_pola)
cavebot.OGIEN_UNIKAJ = 1

# 3b. droga A*: omija ogień, bez objazdu (korytarz 1 pole) brak drogi; pokrętło wyłącza
s = Swiat(pas(95, 110, 98, 102)); b = zrob(s)
d0 = b.droga((100, 100, 7), (106, 100), dlugosc=0, skosy=False)
ogien_w(b, s, (103, 100))
d1 = b.droga((100, 100, 7), (106, 100), dlugosc=0, skosy=False)
sprawdz("3b1 droga omija ogień", d0 is not None and len(d0) == 6 and d1 is not None and (103, 100, 7) not in d1
        and len(d1) == 8, f"{d0} {d1}")
d2 = b.droga((100, 100, 7), (103, 100), dlugosc=0, skosy=False)
sprawdz("3b2 pole ognia jako cel (dlugosc 0): brak drogi", d2 is None)
d3 = b.droga((100, 100, 7), (103, 100), dlugosc=1, skosy=False)
sprawdz("3b3 cel obok ognia (dlugosc 1) dochodzimy, nie wchodząc w ogień", d3 and (103, 100, 7) not in d3, f"{d3}")
cavebot.OGIEN_UNIKAJ = 0
sprawdz("3b4 pokrętło 0: droga przez ogień", (103, 100, 7) in b.droga((100, 100, 7), (106, 100), skosy=False))
cavebot.OGIEN_UNIKAJ = 1
s2 = Swiat(pas(95, 110, 100, 100)); b2 = zrob(s2)
ogien_w(b2, s2, (103, 100))
sprawdz("3b5 korytarz zamknięty ogniem: brak drogi (nie wchodzimy)", b2.droga((100, 100, 7), (106, 100), skosy=False) is None)
sprawdz("3b6 _pole_zablokowane", b2._pole_zablokowane((103, 100, 7), ()) and not b2._pole_zablokowane((104, 100, 7), ()))
ogien_w(b2, s2, (100, 100))
sprawdz("3b7 pole startu nie blokuje drogi z ognia", b2.droga((100, 100, 7), (102, 100), skosy=False) is not None)
b2.ogien_pola.clear(); ogien_w(b2, s2, (200, 200))
sprawdz("3b8 ogień na innym polu nie przeszkadza", b2.droga((100, 100, 7), (106, 100), skosy=False) is not None)

# 3c. krok_do nie wchodzi w ogień
s = Swiat(pas(95, 110, 100, 100)); b = zrob(s)
ogien_w(b, s, (101, 100))
r = b.krok_do((105, 100))
sprawdz("3c1 krok_do: brak kroku w ogień", r is False and all(k != "Right" for k, _ in s.kroki)
        and tuple(s.poz) == (100, 100, 7), f"{s.kroki}")
b.ogien_pola.clear()
r = b.krok_do((105, 100))
sprawdz("3c2 bez ognia: krok", r and s.poz[0] == 101)
# krok_prosto
s = Swiat(pas(95, 110, 99, 101)); b = zrob(s)
ogien_w(b, s, (101, 100))
b.krok_prosto((104, 100), (100, 100, 7), pauza=False)
sprawdz("3c3 krok_prosto: nie w ogień", "Right" not in s.klawisze, s.klawisze)

# 3d. zejście z ognia
s = Swiat(pas(95, 110, 100, 100)); b = zrob(s)
ogien_w(b, s, (100, 100), (101, 100))
L0 = len(LOGI)
sprawdz("3d1 _ogien_wyjdz: krok na wolne pole", b._ogien_wyjdz((100, 100, 7), s.t) is True and tuple(s.poz) == (99, 100, 7)
        and s.kroki == [("Left", (99, 100))], f"{s.kroki}")
sprawdz("3d2 log zejścia", any("[OGIEN] stoję na ogniu (100,100), schodzę na (99,100)" in l for l in LOGI[L0:]))
sprawdz("3d3 poza ogniem: nic", b._ogien_wyjdz((99, 100, 7), s.t + 5) is False)
# pas ognia 3 pola: wychodzimy przez ogień do najbliższego wolnego
s = Swiat(pas(95, 110, 100, 100), poz=(100, 100, 7)); b = zrob(s)
ogien_w(b, s, (99, 100), (100, 100), (101, 100), (102, 100))
b._ogien_wyjdz((100, 100, 7), s.t)
sprawdz("3d4 wokół ogień: najkrótszy wyjście (Left przez (99,100) do (98,100))", s.kroki and s.kroki[0][0] == "Left", s.kroki)
# stwór zajmuje wolne pole: obchodzi
s = Swiat(pas(95, 110, 99, 101)); b = zrob(s)
ogien_w(b, s, (100, 100))
s.stwory = [{"id": 5, "nazwa": "Troll", "gracz": False, "x": 100, "y": 99, "z": 7, "hp": 100},
            {"id": 6, "nazwa": "Troll", "gracz": False, "x": 99, "y": 100, "z": 7, "hp": 100}]
b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
b._ogien_wyjdz((100, 100, 7), s.t)
sprawdz("3d5 pola ze stworami pomijane", s.kroki and s.kroki[0][0] in ("Down", "Right"), s.kroki)
# krok nie przesunął postaci: ten krok jest pamiętany jako zły, następny inny
s = Swiat(pas(95, 110, 99, 101)); b = zrob(s)
ogien_w(b, s, (100, 100))
s.wolne.discard((100, 99)); s.wolne.discard((99, 100)); s.wolne.discard((100, 101))   # świat: tylko Right wolne
b._ogien_wyjdz((100, 100, 7), s.t)
s.t += 1.0
b._ogien_wyjdz((100, 100, 7), s.t)
sprawdz("3d6 nieudany krok nie jest powtarzany", len(s.kroki) >= 1 and s.kroki[0][0] == "Up"
        and (len(s.kroki) < 2 or s.kroki[1][0] != "Up"), s.kroki)
# rate limit
s = Swiat(pas(95, 110, 100, 100)); b = zrob(s)
ogien_w(b, s, (100, 100), (99, 100), (101, 100)); b._ogien_wyjdz((100, 100, 7), s.t)
n = len(s.kroki)
b._ogien_wyjdz(tuple(s.poz), s.t + 0.1)
sprawdz("3d7 nie częściej niż OGIEN_KROK_S", len(s.kroki) == n)

# 3e. tick: zejście z ognia przed resztą (też przy wyłączonym LOOT/ML), pokrętło 0 = nic
s = Swiat(pas(90, 120, 100, 100)); b = zrob(s)
b.ogien_odczyt = lambda: {(0, 0)}
b.tick()
sprawdz("3e1 tick: schodzimy z pola ognia", s.kroki and s.kroki[0][0] in ("Left", "Right")
        and (s.poz[0] != 100), f"{s.kroki} {s.poz}")
sprawdz("3e2 po zejściu ogień zostaje w pamięci jako przeszkoda", (100, 100, 7) in b.ogien_pola)
cavebot.OGIEN_UNIKAJ = 0
s = Swiat(pas(90, 120, 100, 100)); b = zrob(s); b.ogien_odczyt = lambda: {(0, 0)}
L0 = len(LOGI)
b.tick()
sprawdz("3e3 OGIEN_UNIKAJ=0: tick nie schodzi z ognia (idzie trasą w prawo)", not b.ogien_pola
        and not any(l.startswith("[OGIEN]") for l in LOGI[L0:]) and s.poz[0] >= 100, f"{s.kroki} {s.poz}")
cavebot.OGIEN_UNIKAJ = 1

# 3f. loot: zwłoki na ogniu nie są zbierane; po zgaśnięciu wracają
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
zw = (102, 100, 7)
ogien_w(b, s, (102, 100))
b.odloz_zwloki(zw, nowe=True)
sprawdz("3f1 zwloki_do_zebrania pomija zwłoki na ogniu", b.zwloki_do_zebrania((100, 100, 7)) is None
        and any(z == zw for z, _ in b.zwloki_czekajace))
L0 = len(LOGI)
w = b.zbierz_loot(zw)
sprawdz("3f2 zbierz_loot: przerwany, loot.zbierz nie wołany, nie wchodzimy", w == "przerwany" and not s.zbierz
        and tuple(s.poz) == (100, 100, 7), f"{w} {s.zbierz} {s.poz}")
sprawdz("3f3 zwłoki odłożone na później + log", any(z == zw for z, _ in b.zwloki_czekajace)
        and any("[OGIEN] zwłoki" in l for l in LOGI[L0:]))
b.ogien_pola.clear(); s.t += cavebot.OGIEN_LOOT_CHLOD_S + 1
sprawdz("3f4 po zgaśnięciu ognia zwłoki wracają", b.zwloki_do_zebrania((100, 100, 7)) == zw)
# zwłoki obok ognia: normalnie zbierane i droga nie przez ogień
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
ogien_w(b, s, (101, 100))
w = b.zbierz_loot((103, 100, 7))
sprawdz("3f5 zwłoki poza ogniem: loot, droga bokiem", w == "ok" and s.zbierz == [(103, 100, 7)]
        and all(n != (101, 100) for _, n in s.kroki), f"{w} {s.kroki}")

# 3g. klik: klient poprowadziłby klik przez ogień -> idziemy sami bokiem
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s, klik=True)
ogien_w(b, s, (103, 100))
b.idz_do((106, 100), (100, 100, 7))
sprawdz("3g1 klik przez ogień zastąpiony krokiem", not s.kliki and len(s.kroki) == 1, f"{s.kliki} {s.kroki}")
for _ in range(12):
    if s.poz[0] >= 106: break
    b.idz_do((106, 100), tuple(s.poz) + (7,) if len(s.poz) == 2 else tuple(s.poz))
sprawdz("3g2 omijamy ogień bokiem, nigdy w niego nie wchodząc; za ogniem znów klik", s.poz[0] >= 105
        and all(n != (103, 100) for _, n in s.kroki) and s.kliki, f"{s.kroki} {s.kliki}")
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s, klik=True)
b.idz_do((106, 100), (100, 100, 7))
sprawdz("3g3 bez ognia klik jak dawniej", s.kliki and not s.kroki, f"{s.kliki} {s.kroki}")
# korytarz zamknięty ogniem: czeka, po OGIEN_CZEKAJ_MAX_S ignoruje
s = Swiat(pas(90, 120, 100, 100)); b = zrob(s, klik=True)
ogien_w(b, s, (103, 100))
for _ in range(3):
    s.t += 1.0; b._ogien_krok((100, 100, 7), (106, 100))
sprawdz("3g4 zamknięta droga: czekamy przed ogniem (bez kroku w ogień)", not any(n == (103, 100) for _, n in s.kroki)
        and s.poz[0] <= 102 and not s.kliki, f"{s.kroki} {s.poz}")
s.t += cavebot.OGIEN_CZEKAJ_MAX_S + 1
b.ogien_pola[(103, 100, 7)] = s.t
for _ in range(3):
    s.t += 1.0; b._ogien_krok(tuple(s.poz), (106, 100))
sprawdz("3g5 po czekaniu ignoruje ogień na OGIEN_IGNORUJ_S", b.ogien_ignoruj_do > s.t - 5
        and any("ignoruję go" in l for l in LOGI), f"{b.ogien_ignoruj_do} {s.t}")

# --- 6. P6: maska stałych pól, rzadszy log, podsumowanie
cavebot.OGIEN_MASKA_TYLKO_SCIANY = 0   # starsze testy P6 zakładają maskę także dla pól przechodnich
sprawdz("6a domyślne: OGIEN_STALY 1, OGIEN_LOG_S 10 (z pliku)", cavebot.OGIEN_STALY == 1 and "OGIEN_LOG_S = 10.0" in open(cavebot.__file__).read())
sprawdz("6b ZAKRESY pokręteł P6", pokretla.ZAKRESY.get("OGIEN_STALY") == (0, 1) and pokretla.ZAKRESY.get("OGIEN_LOG_S") == (1.0, 60.0)
        and pokretla.ZAKRESY.get("OGIEN_ODSWIEZ_WALKA_S") == (0.8, 5.0)
        and pokretla.waliduj({"OGIEN_STALY": 0}, {"OGIEN_STALY": 1})[0] == {})
cavebot.OGIEN_LOG_S = 10.0
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
L0 = len(LOGI)
b.ogien_odczyt = lambda: {(2, 0)}
for _ in range(25):                         # to samo pole 25 razy w ~11 min (krok 27 s)
    s.t += 27.0; b._ogien_tick((100, 100, 7), s.t, wymus=True)
sprawdz("6c pole widziane 25x w 11 min jest stałe", (102, 100, 7) in b.ogien_stale, b.ogien_stale)
logi = [l for l in LOGI[L0:] if l.startswith("[OGIEN] pola:")]
sprawdz("6d dopóki nie stałe, logowane raz; po uznaniu za stałe brak kolejnych wpisów", len(logi) == 1, logi)
sprawdz("6e stałe pole nie blokuje drogi ani kliku",
        b._ogien_blok((100, 100, 7)) == [] and not b._ogien_na_drodze((100, 100, 7), (106, 100)))
sprawdz("6f ale zwłoki/zejście z ognia nadal widzą pole", b._ogien_na((102, 100, 7)) and (102, 100) in b._ogien_xy(7))
# nowe pole obok: zmienne, log, blok
b.ogien_odczyt = lambda: {(2, 0), (3, 0)}
s.t += 27.0; b._ogien_tick((100, 100, 7), s.t, wymus=True)
logi = [l for l in LOGI[L0:] if l.startswith("[OGIEN] pola:")]
sprawdz("6g nowe pole obok: log tylko z nowym polem, blokuje drogę",
        len(logi) == 2 and "(103,100)" in logi[-1] and "(102,100)" not in logi[-1]
        and b._ogien_blok((100, 100, 7)) == [(103, 100, 7)], logi)
# pokrętło OGIEN_STALY=0: wszystko jak dawniej
cavebot.OGIEN_STALY = 0
sprawdz("6h OGIEN_STALY=0: stałe pole znów blokuje", (102, 100, 7) in b._ogien_blok((100, 100, 7)))
cavebot.OGIEN_STALY = 1
# ściana z mapy: stałe od razu
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
_f0 = b.mapa.flagi
b.mapa.flagi = lambda x, y, z: 5 if (x, y) == (101, 100) else _f0(x, y, z)
b.ogien_odczyt = lambda: {(1, 0), (0, 1)}
b._ogien_tick((100, 100, 7), 5.0, wymus=True)
sprawdz("6i pole na ścianie mapy stałe od razu, zwykłe nie", b.ogien_stale == {(101, 100, 7)}, b.ogien_stale)
# log co najwyżej co OGIEN_LOG_S i podsumowanie co OGIEN_PODSUMOWANIE_S
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
L0 = len(LOGI)
for i in range(6):
    b.ogien_odczyt = (lambda i=i: {(i % 2 + 1, 0)})
    s.t += 3.0; b._ogien_tick((100, 100, 7), s.t, wymus=True)     # zbiór zmienia się co 3 s (18 s)
logi = [l for l in LOGI[L0:] if l.startswith("[OGIEN] pola:")]
sprawdz("6j zmiany zbioru co 3 s: log nie częściej niż co 10 s", 1 <= len(logi) <= 2, logi)
s.t += cavebot.OGIEN_PODSUMOWANIE_S + 1; b._ogien_tick((100, 100, 7), s.t, wymus=True)
sprawdz("6k podsumowanie 'ogień: N stałych, M zmiennych'", any("[OGIEN] ogień:" in l and "zmiennych" in l for l in LOGI[L0:]))
# WALKA bez zmiennych pól: rzadsze wykrycia przy OGIEN_ODSWIEZ_WALKA_S > OGIEN_ODSWIEZ_S
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s); b.stan = "WALKA"
b.ogien_odczyt = lambda: set()
cavebot.OGIEN_ODSWIEZ_WALKA_S = 3.0
s.t = 100.0; b._ogien_tick((100, 100, 7), s.t); t1 = b.ogien_t
s.t += 1.0; b._ogien_tick((100, 100, 7), s.t); t2 = b.ogien_t
s.t += 3.0; b._ogien_tick((100, 100, 7), s.t); t3 = b.ogien_t
cavebot.OGIEN_ODSWIEZ_WALKA_S = 0.8
sprawdz("6l WALKA: wykrycia co 3 s zamiast 0,8", t1 == 100.0 and t2 == 100.0 and t3 == 104.0, (t1, t2, t3))
cavebot.OGIEN_LOG_S = 1.0


# --- 7. R1a: maska tylko dla pól-ścian wg mapy, zasiew i zapis pliku ---
import json as _json, tempfile as _tf, os as _os
cavebot.OGIEN_MASKA_TYLKO_SCIANY = 1
sprawdz("7a domyślne i ZAKRES OGIEN_MASKA_TYLKO_SCIANY", "OGIEN_MASKA_TYLKO_SCIANY = 1 " in open(cavebot.__file__).read()
        and pokretla.ZAKRESY.get("OGIEN_MASKA_TYLKO_SCIANY") == (0, 1)
        and pokretla.KIERUNEK.get("OGIEN_MASKA_TYLKO_SCIANY") == "nie_nizej"
        and '"OGIEN_MASKA_TYLKO_SCIANY"' in open(str(Path(_katalog) / "na_zywo.przyklad.json")).read())
_tmp = _os.path.join(_tf.mkdtemp(), "ogien_stale.json")
cavebot.PLIK_OGIEN_STALE = _tmp
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
b.ogien_odczyt = lambda: {(2, 0)}
for _ in range(25):
    s.t += 27.0; b._ogien_tick((100, 100, 7), s.t, wymus=True)
sprawdz("7b pole przechodnie wykryte 25x w 11 min nie wchodzi do maski", (102, 100, 7) not in b.ogien_stale, b.ogien_stale)
sprawdz("7c i blokuje drogę oraz klik", b._ogien_blok((100, 100, 7)) == [(102, 100, 7)] and b._ogien_na_drodze((100, 100, 7), (106, 100)))
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
_f0 = b.mapa.flagi
b.mapa.flagi = lambda x, y, z: 5 if (x, y) == (101, 100) else _f0(x, y, z)
b.ogien_odczyt = lambda: {(1, 0), (0, 1)}
b._ogien_tick((100, 100, 7), 5.0, wymus=True)
sprawdz("7d pole-ściana wchodzi do maski od razu, przechodnie nie", b.ogien_stale == {(101, 100, 7)}, b.ogien_stale)
zap = _json.load(open(_tmp))
sprawdz("7e zapis pliku po zmianie", zap["pola"] == [[101, 100, 7]], zap)
# wczytanie: ściana zostaje, pole przechodnie z pliku odpada
_json.dump({"pola": [[101, 100, 7], [105, 100, 7]]}, open(_tmp, "w"))
s = Swiat(pas(90, 120, 98, 102))
_zr = cavebot.Cavebot
b = zrob(s); b.mapa.flagi = lambda x, y, z: 5 if (x, y) == (101, 100) else _f0(x, y, z)
b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("7f wczytanie maski z pliku (tylko ściany wg mapy)", b.ogien_stale == {(101, 100, 7)}, b.ogien_stale)
cavebot.OGIEN_MASKA_TYLKO_SCIANY = 0
b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("7g pokrętło 0: wczytuje wszystko z pliku", b.ogien_stale == {(101, 100, 7), (105, 100, 7)}, b.ogien_stale)
cavebot.OGIEN_MASKA_TYLKO_SCIANY = 1
# prawdziwy ogień pod nami nadal daje "schodzę"
s = Swiat(pas(90, 120, 98, 102)); b = zrob(s)
ogien_w(b, s, (100, 100))
L0 = len(LOGI)
sprawdz("7h ogień pod nami: wychodzimy", b._ogien_wyjdz(tuple(s.poz), s.t) is True and bool(s.kroki), s.kroki)
cavebot.PLIK_OGIEN_STALE = None

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
