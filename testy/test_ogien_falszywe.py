"""27.10 (wydra, korytarz z8 (32494..32499, 32297..32302)): lista wyjątków trasy/ogien_stale_falszywe.json. Pola z listy nie wchodzą do
trasy/ogien_stale.json przy wczytaniu ani przy zapisie (8 procesów zapisuje ten plik w całości, więc samo skasowanie wpisów wracało);
pola spoza listy działają jak dotąd; brak/uszkodzenie listy = zachowanie sprzed zmiany. Na atrapach, bez X11 (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, json, tempfile
sys.dont_write_bytecode = True
_katalog = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _katalog)
from pathlib import Path
import cavebot, bot
import mapa as _mapa_mod

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0; cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
cavebot.OGIEN_UNIKAJ = 1; cavebot.OGIEN_MASKA_TYLKO_SCIANY = 1
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
        s.t = 0.0; s.poz = list(poz); s.stwory = []; s.wolne = set(wolne)
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 190, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k): return None

def zrob():
    """Mapa 90..120 x 98..102 (flaga 1); pola-ściany (101,100), (103,100), (105,100) ustawiamy flagą 5 (widziane + ściana)."""
    s = Swiat([(x, y) for x in range(90, 121) for y in range(98, 103)])
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [], ile_jedzenia=lambda: None)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5", mapa=AtrapaMapy(s.wolne))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    f0 = b.mapa.flagi
    b.mapa.flagi = lambda x, y, z: 5 if (x, y) in {(101, 100), (103, 100), (105, 100)} else f0(x, y, z)
    return s, b

kat = Path(tempfile.mkdtemp())
stale, falsz = kat / "ogien_stale.json", kat / "ogien_stale_falszywe.json"
cavebot.PLIK_OGIEN_STALE, cavebot.PLIK_OGIEN_FALSZYWE = stale, falsz

# 1. wczytanie: pole z listy wyjątków odpada, pozostałe ściany zostają
stale.write_text(json.dumps({"pola": [[101, 100, 7], [103, 100, 7], [105, 100, 7]]}))
falsz.write_text(json.dumps({"pola": [[103, 100, 7]]}))
s, b = zrob(); b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("1a wczytanie pomija pole z listy wyjątków", b.ogien_stale == {(101, 100, 7), (105, 100, 7)}, b.ogien_stale)
sprawdz("1b zwykły konstruktor też (zasiew w __init__)", (103, 100, 7) not in b.ogien_stale and (101, 100, 7) in b.ogien_stale)
# 1c: wyjątek dotyczy piętra i pola, nie samego (x, y)
stale.write_text(json.dumps({"pola": [[103, 100, 7], [103, 100, 8]]}))
s, b = zrob(); b.ogien_stale = set(); b.mapa.flagi = lambda x, y, z: 5; b._ogien_stale_wczytaj()
sprawdz("1c wyjątek (103,100,7) nie dotyczy (103,100,8)", b.ogien_stale == {(103, 100, 8)}, b.ogien_stale)

# 2. zapis: pamięć procesu ma pole z listy (stary wpis, wykrycie na ekranie), plik go nie dostaje
s, b = zrob()
b.ogien_stale = {(101, 100, 7), (103, 100, 7)}
b._ogien_stale_zapisz()
zap = json.loads(stale.read_text())
sprawdz("2a zapis nie przywraca pola z listy wyjątków", zap["pola"] == [[101, 100, 7]], zap["pola"])
sprawdz("2b pamięć procesu nietknięta (droga i klik bez zmian)", b.ogien_stale == {(101, 100, 7), (103, 100, 7)})

# 3. wykrycie na ekranie: pole-ściana z listy trafia do pamięci (jak dotąd), ale nie do pliku; pole spoza listy trafia do obu
s, b = zrob(); b.ogien_stale = set()
b.ogien_odczyt = lambda: {(3, 0), (5, 0)}          # (103,100) z listy wyjątków, (105,100) spoza niej
b._ogien_tick((100, 100, 7), 5.0, wymus=True)
zap = json.loads(stale.read_text())
sprawdz("3a wykryte pole-ściana z listy: w pamięci", (103, 100, 7) in b.ogien_stale, b.ogien_stale)
sprawdz("3b ... ale nie w pliku; pole spoza listy w pliku", zap["pola"] == [[105, 100, 7]], zap["pola"])
sprawdz("3c pole spoza listy nadal działa: stałe, nie blokuje A*", (105, 100, 7) in b.ogien_stale
        and (105, 100) not in {(x, y) for x, y, _ in b._ogien_blok((100, 100, 7))})

# 4. zgodność wstecz: brak listy, pusta lista, uszkodzona lista = dotychczasowe zachowanie
stale.write_text(json.dumps({"pola": [[101, 100, 7], [103, 100, 7]]}))
falsz.unlink()
s, b = zrob(); b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("4a brak pliku wyjątków: wczytuje wszystko", b.ogien_stale == {(101, 100, 7), (103, 100, 7)}, b.ogien_stale)
b._ogien_stale_zapisz()
sprawdz("4b brak pliku wyjątków: zapisuje wszystko", json.loads(stale.read_text())["pola"] == [[101, 100, 7], [103, 100, 7]])
falsz.write_text(json.dumps({"pola": []}))
s, b = zrob(); b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("4c pusta lista: wczytuje wszystko", b.ogien_stale == {(101, 100, 7), (103, 100, 7)}, b.ogien_stale)
falsz.write_text("{nie json")
L0 = len(LOGI)
s, b = zrob(); b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("4d uszkodzona lista: wczytuje wszystko i loguje błąd", b.ogien_stale == {(101, 100, 7), (103, 100, 7)}
        and any("listy fałszywych pól" in l for l in LOGI[L0:]), LOGI[L0:])
cavebot.PLIK_OGIEN_FALSZYWE = None
s, b = zrob(); b.ogien_stale = set(); b._ogien_stale_wczytaj()
sprawdz("4e brak ścieżki (testy bez pliku): bez filtra", b.ogien_stale == {(101, 100, 7), (103, 100, 7)})
cavebot.PLIK_OGIEN_STALE = cavebot.PLIK_OGIEN_FALSZYWE = None

# 6. epizody: lista "epizody_bez_hp" (korekta Karola 27.10: (32497,32301) to błąd przypisania, prawdziwy ogień to (32497,32300))
epi = kat / "ogien_epizody.json"
cavebot.PLIK_OGIEN_EPIZODY, cavebot.PLIK_OGIEN_FALSZYWE = epi, falsz
def ep_zapis(**pola):
    epi.write_text(json.dumps({"pola": {k: {"n": 5, "godz": [9, 10], "hp": v, "ost": 1.0} for k, v in pola.items()}}))
falsz.write_text(json.dumps({"pola": [], "epizody_bez_hp": [[103, 100, 7]]}))
ep_zapis(**{"103,100,7": True, "104,100,7": True})
s, b = zrob()
sprawdz("6a wczytanie: hp pola z listy = False, pole spoza listy zostaje hp=True", b.ogien_epizody["103,100,7"]["hp"] is False
        and b.ogien_epizody["104,100,7"]["hp"] is True and b.ogien_epizody["103,100,7"]["n"] == 5, b.ogien_epizody)
sprawdz("6a2 parzące pola (A*): tylko spoza listy", b._ogien_parzy_dane(7) == {(104, 100)}, b._ogien_parzy_dane(7))
# scalanie: pamięć i plik mają hp=True (stary bot zapisał), pole z listy gaśnie
b.ogien_epizody["103,100,7"]["hp"] = True
b._ogien_epizody_scal()
sprawdz("6b scalenie z plikiem nie przywraca hp na polu z listy", b.ogien_epizody["103,100,7"]["hp"] is False and b.ogien_epizody["104,100,7"]["hp"] is True)
# zapis: pamięć hp=True (np. sprzed listy), plik dostaje hp=False tylko dla pola z listy; reszta danych bez zmian
b.ogien_epizody["103,100,7"]["hp"] = True; b.ogien_ep_brudne = True
b._ogien_epizody_zapisz(1e9, wymus=True)
zp = json.loads(epi.read_text())["pola"]
sprawdz("6c zapis: hp=False dla pola z listy, n/godz bez zmian, pole spoza listy hp=True", zp["103,100,7"]["hp"] is False and zp["103,100,7"]["n"] == 5
        and zp["103,100,7"]["godz"] == [9, 10] and zp["104,100,7"]["hp"] is True, zp)
# stary bot (hp=True w pliku) po zapisie innego procesu: nowy bot nadal gasi
ep_zapis(**{"103,100,7": True, "104,100,7": True})
s, b = zrob()
sprawdz("6d plik ponownie z hp=True (zapis starego bota): wczytanie znów gasi", b.ogien_epizody["103,100,7"]["hp"] is False)
# tick: spadek HP tuż po wejściu na pole z listy NIE ustawia hp; na polu spoza listy ustawia (kontrola)
def spadek(pole):
    s, b = zrob(); b.ogien_epizody = {}; b.ogien_wall = lambda: 1.8e9 + s.t
    s.t += 100.0
    b.ogien_hp_hist = [(s.t - 1.0, 100.0), (s.t, 90.0)]
    b.ogien_odczyt = lambda: {(0, 0)}
    b._ogien_tick(pole, s.t, wymus=True)
    return b.ogien_epizody.get(f"{pole[0]},{pole[1]},{pole[2]}")
e103, e104 = spadek((103, 100, 7)), spadek((104, 100, 7))
sprawdz("6e spadek HP na polu z listy: hp nie ustawione", e103 is not None and e103["hp"] is False, e103)
sprawdz("6f spadek HP na polu spoza listy: hp=True (zachowanie bez zmian)", e104 is not None and e104["hp"] is True, e104)
# zgodność wstecz: lista bez klucza / bez pliku / uszkodzona = jak dawniej
ep_zapis(**{"103,100,7": True, "104,100,7": True})      # (6e zapisał plik przez tick)
falsz.write_text(json.dumps({"pola": []}))
s, b = zrob()
sprawdz("6g brak klucza epizody_bez_hp: hp bez zmian", b.ogien_epizody["103,100,7"]["hp"] is True)
falsz.unlink()
s, b = zrob()
sprawdz("6h brak pliku listy: hp bez zmian", b.ogien_epizody["103,100,7"]["hp"] is True)
falsz.write_text("{zepsute")
s, b = zrob()
sprawdz("6i uszkodzona lista: hp bez zmian", b.ogien_epizody["103,100,7"]["hp"] is True)
cavebot.PLIK_OGIEN_EPIZODY = cavebot.PLIK_OGIEN_FALSZYWE = None

# 5. dane w repo (gwarancja, że nikt nie dopisze prawdziwego ognia do wyjątków ani do maski stałej)
tr = Path(_katalog) / "trasy"
fl = {tuple(p[:3]) for p in json.loads((tr / "ogien_stale_falszywe.json").read_text())["pola"]}
st = {tuple(p[:3]) for p in json.loads((tr / "ogien_stale.json").read_text())["pola"]}
ep = json.loads((tr / "ogien_epizody.json").read_text())["pola"]
sprawdz("5a lista wyjątków: 12 pól piętra 8 w korytarzu wydry", len(fl) == 12 and all(z == 8 and 32494 <= x <= 32499 and 32297 <= y <= 32302 for x, y, z in fl), len(fl))
# (5b celowo brak: żywe boty na starym kodzie dopisują te pola do ogien_stale.json do swojego restartu; sprawdzenie ręczne w STAN.md)
sprawdz("5c (32497,32301,8) nie jest na liście ścian ani w masce stałej", (32497, 32301, 8) not in fl and (32497, 32301, 8) not in st)
_bez = json.loads((tr / "ogien_stale_falszywe.json").read_text()).get("epizody_bez_hp", [])
# (hp w epizodach dla (32497,32301,8) celowo bez asercji: żywe boty na starym kodzie przywracają hp:true przy zapisie do swojego restartu)
sprawdz("5d epizody_bez_hp = dokładnie (32497,32301,8)", _bez == [[32497, 32301, 8]], _bez)
sprawdz("5d2 prawdziwy ogień (32497,32300,8) hp:true, mini ogień (32496/32498,32300) bez hp", ep["32497,32300,8"]["hp"] is True
        and ep["32496,32300,8"]["hp"] is False and ep["32498,32300,8"]["hp"] is False)
sprawdz("5e domyślna ścieżka bota to trasy/ogien_stale_falszywe.json", 'trasy" / "ogien_stale_falszywe.json"' in open(cavebot.__file__).read())

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
