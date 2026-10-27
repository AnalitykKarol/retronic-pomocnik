"""24.10 wydra "utknęła i przeszła przez ogień" (trolle_patrol, lejek (32497,32299)-(32498,32301), z8). Offline, na atrapach
(RETRONIC_TESTY=1): okno podpalenia po wejściu na ZNANE parzące pole (OGIEN_PODPALENIE_ZNANE), scalanie epizodów
(OGIEN_EPIZODY_SCAL), głośna porażka skosu, geometria lejka (A* nigdy przez ogień, skos wychodzi z kieszeni)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json as _json, sys, tempfile as _tf, types
sys.dont_write_bytecode = True
_katalog = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _katalog)
import cavebot, bot
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
cavebot.OGIEN_PARZY_BUFOR = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))

Z = 8
# pola przechodnie lejka wg mapy (mapa.Mapa().przechodnie, 24.10); reszta w atrapie to ściany
LEJEK = [(32495, 32298), (32495, 32299), (32496, 32298), (32496, 32299), (32496, 32300), (32497, 32299), (32497, 32300),
         (32497, 32301), (32498, 32300), (32498, 32301), (32498, 32302), (32499, 32302), (32499, 32303), (32500, 32303),
         (32499, 32304)]
H = (32497, 32300, Z)       # parzy (hp:true), n=52 w trasy/ogien_epizody.json
K1 = (32497, 32301, Z)      # fałszywie oznaczone 12:21:30 (w danych: n=34, hp:false, w masce danych)
EP_H = {"n": 52, "godz": [8, 9], "hp": True, "ost": 0.0}
EP_K1 = {"n": 34, "godz": [8, 9, 10], "hp": False, "ost": 0.0}


FLAGI = {(32497, 32300): 3}


class AtrapaMapy(_mapa_mod.Mapa):
    def __init__(s, wolne, z=Z):
        s._dane, s._spis, s._bloki, s.wersja = b"", {}, {}, 1
        pola_ = {tuple(p[:2]): 1 for p in wolne}
        pola_.update({k: v for k, v in FLAGI.items() if k in pola_})  # jak w prawdziwej mapie: H ma flagę 3 (schody/dziura), A* go omija
        for bx, by in {(x >> 6, y >> 6) for x, y in pola_}:
            b = bytearray(bytes([5, 114, 0]) * 4096)
            for (x, y), f in pola_.items():
                if (x >> 6, y >> 6) == (bx, by):
                    b[((y & 63) * 64 + (x & 63)) * 3] = f
            s._bloki[_mapa_mod._klucz_bloku(bx << 6, by << 6, z)] = bytes(b)


class Swiat:
    def __init__(s, poz, wolne=LEJEK, skos_dziala=True):
        s.t = 1000.0; s.poz = list(poz); s.kroki = []; s.wolne = set(wolne); s.skos_dziala = skos_dziala
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 190, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": Z, "hp": 100}]}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return (p.s.poz[0], p.s.poz[1], Z)
    def klawisz(p, k): pass
    def krok(p, k):
        s = p.s; d = bot.KIERUNKI[k]; s.t += 1.5
        n = (s.poz[0] + d[0], s.poz[1] + d[1]); s.kroki.append((k, n))
        if n not in s.wolne:
            return None
        s.poz[0], s.poz[1] = n
        return (n[0], n[1], Z)
    def krok_skos(p, dx, dy):
        s = p.s; s.t += 1.5
        n = (s.poz[0] + dx, s.poz[1] + dy); s.kroki.append((("skos", dx, dy), n))
        if not s.skos_dziala or n not in s.wolne:
            return None
        s.poz[0], s.poz[1] = n
        return (n[0], n[1], Z)


def zrob(poz, ep=None, pola=(), cel=(32497, 32299, Z), skos_dziala=True):
    s = Swiat(poz, skos_dziala=skos_dziala)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [], ile_jedzenia=lambda: None)
    b = cavebot.Cavebot(P(s), [cel], zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij,
                        zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5", mapa=AtrapaMapy(s.wolne))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.ogien_epizody = {}
    for k, e in (ep or {}).items():
        b.ogien_epizody[k] = dict(e)
    b._ogien_dane_przelicz()
    for p in pola:
        b.ogien_pola[p] = s.t
    b.ogien_wall = lambda: 1.8e9 + s.t
    return s, b


def tick(b, s, poz, dt, wzgl, hp=None):
    """Jeden obieg wykrywania ognia: postać na poz, wykryte pola względne `wzgl`, opcjonalnie spadek HP (od, do) w ostatniej s."""
    s.t += dt
    if hp is not None:
        b.ogien_hp_hist = [(s.t - 1.0, hp[0]), (s.t, hp[1])]
    b.ogien_odczyt = lambda: wzgl
    b._ogien_tick(poz, s.t, wymus=True)


EPIZODY = {"32497,32300,8": EP_H, "32497,32301,8": EP_K1}

# --- 1. odtworzenie 12:21:19-12:21:30: przejście przez znane H, 11 s później spadek HP (podpalenie) na K1 ------------------
cavebot.OGIEN_PODPALENIE_ZNANE = 0
s, b = zrob((32497, 32300), EPIZODY)
assert K1 in b.ogien_dane_maska
tick(b, s, H, 1.0, {(0, 0)}, hp=(100.0, 91.0))        # wejście na H, HP 100 -> 91 (trafienie ognia)
tick(b, s, K1, 11.0, {(0, 0)}, hp=(91.0, 87.0))       # 11 s później na K1: spadek 4 pp z podpalenia
sprawdz("1a USTERKA (pokrętło 0): podpalenie z H fałszywie oznacza K1 jako parzące", b.ogien_epizody["32497,32301,8"]["hp"] is True)
sprawdz("1b USTERKA (pokrętło 0): K1 wypada z maski danych", K1 not in b.ogien_dane_maska)

cavebot.OGIEN_PODPALENIE_ZNANE = 1
s, b = zrob((32497, 32300), EPIZODY)
tick(b, s, H, 1.0, {(0, 0)}, hp=(100.0, 91.0))
sprawdz("1c wejście na znane H otwiera okno podpalenia", b.ogien_podpalony_do >= s.t + cavebot.OGIEN_PODPALENIE_S - 0.01,
        (b.ogien_podpalony_do, s.t))
sprawdz("1d log o wejściu na znane parzące pole", any("wszedłem na znane parzące pole (32497,32300)" in l for l in LOGI))
tick(b, s, K1, 11.0, {(0, 0)}, hp=(91.0, 87.0))
sprawdz("1e POPRAWKA: K1 nie jest oznaczone parzącym przez podpalenie z H", b.ogien_epizody["32497,32301,8"]["hp"] is False)
sprawdz("1f POPRAWKA: K1 zostaje w masce danych", K1 in b.ogien_dane_maska)
tick(b, s, K1, 40.0, {(0, 0)}, hp=(87.0, 83.0))       # 51 s po wejściu na H: nadal podpalenie
sprawdz("1g nadal w oknie po 51 s: bez oznaczenia", b.ogien_epizody["32497,32301,8"]["hp"] is False)

# 1h. nauka NOWYCH pól zostaje: po wygaśnięciu okna spadek HP tuż po wejściu na nieznane pole ognia oznacza je
tick(b, s, K1, cavebot.OGIEN_PODPALENIE_S, set())      # po całym oknie palenia (27.10: 120 s, było 60) od wejścia na H, poza ogniem
INNE = (32498, 32301, Z)
tick(b, s, INNE, 1.0, {(0, 0)}, hp=(100.0, 90.0))      # nowe pole z ogniem pod stopami + spadek HP tuż po wejściu
sprawdz("1h nauka zostaje: po oknie nowe pole z ogniem i spadkiem HP dostaje hp", b.ogien_epizody.get("32498,32301,8", {}).get("hp") is True,
        b.ogien_epizody.get("32498,32301,8"))

# 1i. wejście na NIEZNANE pole z ogniem: bez okna z góry, nauka działa tak jak dawniej (okno otwiera dopiero oznaczenie)
s, b = zrob((32497, 32300), {})
tick(b, s, H, 1.0, {(0, 0)}, hp=(100.0, 90.0))
sprawdz("1i nieznane pole: spadek HP tuż po wejściu nadal je oznacza", b.ogien_epizody["32497,32300,8"]["hp"] is True
        and b.ogien_podpalony_do > s.t)

# 1j. pokrętło 0 i OGIEN_UNIKAJ=0: wejście na znane pole nie otwiera okna
cavebot.OGIEN_PODPALENIE_ZNANE = 0
s, b = zrob((32497, 32300), EPIZODY)
tick(b, s, H, 1.0, {(0, 0)})
sprawdz("1j pokrętło 0: brak okna", b.ogien_podpalony_do == float("-inf"))
cavebot.OGIEN_PODPALENIE_ZNANE = 1
cavebot.OGIEN_UNIKAJ = 0
s, b = zrob((32497, 32300), EPIZODY)
sprawdz("1k OGIEN_UNIKAJ=0: _ogien_podpalenie_znane nic nie robi", b._ogien_podpalenie_znane(H, s.t) is False)
cavebot.OGIEN_UNIKAJ = 1

# 1l. _ogien_wyjdz też otwiera okno (stoimy na znanym polu, ogień widziany)
s, b = zrob((32497, 32300), EPIZODY, pola=[H])
b.ogien_hp_hist = [(s.t - 1.0, 100.0), (s.t, 91.0)]
b._ogien_wyjdz(H, s.t)
sprawdz("1l _ogien_wyjdz na znanym H otwiera okno", b.ogien_podpalony_do > s.t)

# --- 2. scalanie epizodów przy zapisie (wydra 12:21:30: oznaczenie hp zniknęło z pliku) -----------------------------------
_plik = _os.path.join(_tf.mkdtemp(), "ogien_epizody.json")
cavebot.PLIK_OGIEN_EPIZODY = _plik
def zapis_obcy(pola):
    _json.dump({"opis": "obcy proces", "pola": pola}, open(_plik, "w"))
for scal in (0, 1):
    cavebot.OGIEN_EPIZODY_SCAL = scal
    s, b = zrob((32497, 32300), {"32497,32301,8": {"n": 36, "godz": [8, 9], "hp": False, "ost": 5.0}})
    zapis_obcy({"32497,32301,8": {"n": 35, "godz": [10], "hp": True, "ost": 9.0}, "32490,32290,8": EP_H})
    b.ogien_ep_brudne = True
    b._ogien_epizody_zapisz(s.t + 100, wymus=True)
    zap = _json.load(open(_plik))["pola"]
    e = zap["32497,32301,8"]
    if scal:
        sprawdz("2a SCAL=1: cudze hp:true przeżywa zapis, n=max, godziny=suma", e["hp"] is True and e["n"] == 36 and e["godz"] == [8, 9, 10] and e["ost"] == 9.0, e)
        sprawdz("2b SCAL=1: cudze pole też zostaje w pliku i w pamięci", "32490,32290,8" in zap and "32490,32290,8" in b.ogien_epizody)
        sprawdz("2c SCAL=1: pole z cudzym hp wypada z maski danych / jest parzące", (32497, 32301) in b._ogien_parzy_dane(Z))
    else:
        sprawdz("2d USTERKA (SCAL=0): zapis nadpisuje plik i gubi cudze hp:true", e["hp"] is False and "32490,32290,8" not in zap, e)
cavebot.OGIEN_EPIZODY_SCAL = 1
# 2e. uszkodzony plik nie wywraca zapisu
open(_plik, "w").write("{nie json")
s, b = zrob((32497, 32300), EPIZODY)
b.ogien_ep_brudne = True
b._ogien_epizody_zapisz(s.t + 100, wymus=True)
sprawdz("2e uszkodzony plik: zapis nadal działa", _json.load(open(_plik))["pola"]["32497,32300,8"]["hp"] is True
        and any("nie scalę epizodów" in l for l in LOGI))
cavebot.PLIK_OGIEN_EPIZODY = None

# --- 3. geometria lejka -------------------------------------------------------------------------------------------------
# 3a. A* przez lejek nigdy nie wchodzi na ogień (H, K1) - jedyna droga to skos (32497,32299) -> (32498,32300)
for nazwa, ep, pola in (("H znane + widoczny ogień", {"32497,32300,8": EP_H}, [H, K1]), ("H nieznane, brak wykrycia", {}, []),
                        ("H znane, brak wykrycia", {"32497,32300,8": EP_H}, [])):
    s, b = zrob((32496, 32299), ep, pola=pola)
    d = b.droga((32496, 32299, Z), (32499, 32304), dlugosc=0, skosy=True)
    sprawdz(f"3a A* ({nazwa}): droga skosem poza ogniem", d is not None and d[0][:2] == (32497, 32299) and d[1][:2] == (32498, 32300)
            and H not in d and K1 not in d, d)

# 3b. kieszeń (32498,32300): skos wychodzi, gdy działa
s, b = zrob((32498, 32300), {"32497,32300,8": EP_H}, pola=[H, K1])
b.krok_z = ((32498, 32301, Z), s.t - 2)
ruszyl = b.krok_do((32497, 32299, Z))
sprawdz("3b skos z kieszeni (gdy klient go wykona) wychodzi bez wchodzenia na ogień", ruszyl and tuple(s.poz) == (32497, 32299)
        and all(n not in (H[:2], K1[:2]) for _, n in s.kroki), (s.kroki, s.poz))

# 3c. skos nie rusza: porażka jest teraz widoczna w logu (była cicha), skos_zle blokuje ponowienie na SKOS_ZLY_S
LOGI.clear()
s, b = zrob((32498, 32300), {"32497,32300,8": EP_H}, pola=[H, K1], skos_dziala=False)
b.krok_z = ((32498, 32301, Z), s.t - 2)
b.krok_do((32497, 32299, Z))
sprawdz("3c porażka skosu zostawia ślad w logu", any("Skos awaryjny: krok (-1,-1) z (32498,32300) NIE ruszył" in l for l in LOGI), LOGI[-3:])
sprawdz("3d skos_zle i brak kroku na ogień", ((32498, 32300), (32497, 32299)) in b.skos_zle and all(n != H[:2] for _, n in s.kroki), s.kroki)
n0 = len([k for k, _ in s.kroki if isinstance(k, tuple)])
b.krok_do((32497, 32299, Z))
sprawdz("3e drugi obieg w SKOS_ZLY_S nie ponawia skosu (wolne próby nie kosztują 1,5 s co obieg)",
        len([k for k, _ in s.kroki if isinstance(k, tuple)]) == n0)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
