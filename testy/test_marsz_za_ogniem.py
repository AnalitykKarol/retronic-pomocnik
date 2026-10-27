"""27.10 marsz klikiem ZA znanym ogniem z orbity/kieszeni (pokrętło MARSZ_ZA_OGNIEM_ORBITA, domyślnie 0). Wydra, kieszeń (32498,32300) z8,
jedyny prawdziwy ogień (32497,32300) (hp:true, flaga mapy 3): klik w pole za ogniem (32495,32298), pilnowanie co obieg (wejście na ogień,
spadek HP, brak ruchu, limit czasu = Escape), limit prób, pokrętło 0 = jak dotąd. Zeznanie Karola: autowalk omija ogień, gdy cel kliku nie jest
polem ognia. Offline, na atrapach (RETRONIC_TESTY=1), wzór test_wydra_ogien.py."""
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
        s.t = 1000.0; s.poz = list(poz); s.kroki = []; s.klawisze = []; s.kliki = []; s.wolne = set(wolne); s.skos_dziala = skos_dziala
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
    def klawisz(p, k): p.s.klawisze.append(k)
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
                        zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5", mapa=AtrapaMapy(s.wolne),
                        klik=lambda dx, dy: s.kliki.append((dx, dy)))
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



EP = {"32497,32300,8": EP_H, "32497,32301,8": EP_K1}
START = (32498, 32300, Z)
CEL_ORB = (32495, 32298, Z)
ORB = types.SimpleNamespace(aktywna=lambda: True, ep={"cel": CEL_ORB})


def scena(poz=START, orbita=True, skos_zle=True, ep=EP, pola=()):
    s, b = zrob(poz, ep, pola=pola, cel=CEL_ORB)
    if orbita:
        b._straznik = (None, ORB)
    if skos_zle:
        b.skos_zle[(tuple(poz[:2]), (poz[0] - 1, poz[1] - 1))] = s.t + 30.0     # skos z kieszeni już zawiódł
    return s, b


def idz(b, s, cel=(32497, 32299)):
    return b.idz_do(cel, tuple(s.poz) + (Z,), True, krok=cel)


# 1. pokrętło wyłączone (domyślnie): zachowanie jak dziś (zero kliku za ogniem)
sprawdz("1a domyślnie 0", cavebot.MARSZ_ZA_OGNIEM_ORBITA == 0)
s, b = scena()
idz(b, s)
sprawdz("1b pokrętło 0: brak marszu za ogniem, brak kliku", b.marsz_og is None and not s.kliki and not b.marsz_og_proby, s.kliki)

cavebot.MARSZ_ZA_OGNIEM_ORBITA = 1
# 2. warunki startu
s, b = scena(orbita=False); idz(b, s)
sprawdz("2a bez aktywnej naprawy orbity: nie startuje", b.marsz_og is None and not s.kliki)
s, b = scena(skos_zle=False); idz(b, s)
sprawdz("2b skos z tego pola jeszcze nie zawiódł: nie startuje", b.marsz_og is None and not s.kliki)
s, b = scena(ep={"32497,32300,8": dict(EP_H, hp=False)}, pola=[H]); idz(b, s)
sprawdz("2c ogień nieznany (bez hp:true), tylko z ekranu: nie startuje (zwykła ochrona), brak kliku w (32495,32298)", b.marsz_og is None and (-3, -2) not in s.kliki, s.kliki)
s, b = scena(ep={}); idz(b, s)
sprawdz("2d brak ognia w ogóle: nie ta reguła (zwykły klik w sąsiednie pole, bez marszu za ogniem)", b.marsz_og is None and (-3, -2) not in s.kliki, s.kliki)

# 3. start: klik w pole ZA ogniem
s, b = scena()
idz(b, s)
F = b._marsz_og_ogien(Z)
sprawdz("3a klik wysłany w (32495,32298): względem postaci (-3,-2)", s.kliki == [(-3, -2)] and b.marsz_og and b.marsz_og["cel"] == (32495, 32298), (s.kliki, b.marsz_og))
sprawdz("3b cel nie jest polem ognia i leży >= 2 pola od każdego ognia", F == {(32497, 32300)} and (32495, 32298) not in F
        and all(max(abs(32495 - f[0]), abs(32298 - f[1])) >= 2 for f in F), F)
sprawdz("3c kontrola: droga A* bota do celu nie wchodzi na ogień", all(tuple(q[:2]) not in F for q in b.droga(START, (32495, 32298), dlugosc=0)))
sprawdz("3d bez kroków klawiszem i bez Escape przy starcie", not s.kroki and not s.klawisze, (s.kroki, s.klawisze))
n0 = len(s.kliki)
s.t += 0.5; s.poz[0], s.poz[1] = 32497, 32299
idz(b, s)
sprawdz("3e trwający marsz: kolejne wywołanie nie klika i nie robi kroków (klient idzie sam)", len(s.kliki) == n0 and not s.kroki and b.marsz_og is not None, (s.kliki, s.kroki))
s.t += 0.5; s.poz[0], s.poz[1] = 32496, 32299
idz(b, s)
s.t += 0.5; s.poz[0], s.poz[1] = 32495, 32298
idz(b, s)
sprawdz("3f doszedł: marsz zakończony bez Escape", b.marsz_og is None and not s.klawisze, s.klawisze)

# 4. przerwania
s, b = scena(); idz(b, s)
s.t += 0.5; s.poz[0], s.poz[1] = 32497, 32300       # postać na prawdziwym ogniu
w = b._marsz_og_pilnuj(tuple(s.poz) + (Z,), s.t)
sprawdz("4a wejście na pole ognia: przerwanie + Escape", w == "przerwany" and b.marsz_og is None and s.klawisze == ["Escape"], (w, s.klawisze))
s, b = scena(); idz(b, s)
s.t += 0.5; s.poz[0], s.poz[1] = 32497, 32299
b.ogien_hp_hist = [(s.t - 1.0, 100.0), (s.t, 92.0)]
w = b._marsz_og_pilnuj(tuple(s.poz) + (Z,), s.t)
sprawdz("4b spadek HP >= OGIEN_HP_SPADEK_PP: przerwanie + Escape", w == "przerwany" and s.klawisze == ["Escape"], (w, s.klawisze))
s, b = scena(); idz(b, s)
s.t += cavebot.MARSZ_ZA_OGNIEM_BEZ_RUCHU_S + 0.5                                  # postać stoi w kieszeni
w = b._marsz_og_pilnuj(START, s.t)
sprawdz("4c brak ruchu: przerwanie + Escape", w == "przerwany" and s.klawisze == ["Escape"], (w, s.klawisze))
s, b = scena(); idz(b, s)
for i in range(30):
    s.t += 0.5; s.poz[0], s.poz[1] = (32497, 32299) if i % 2 else (32496, 32299)      # kręci się, ale nie dochodzi
    w = b._marsz_og_pilnuj(tuple(s.poz) + (Z,), s.t)
    if w != "idzie":
        break
sprawdz("4d limit czasu marszu: przerwanie", w == "przerwany" and b.marsz_og is None, w)
s, b = scena(); idz(b, s)
b.cel = {"id": 1, "poz": (32490, 32295, Z)}
sprawdz("4e cel do walki: przerwanie", b._marsz_og_pilnuj(START, s.t + 0.2) == "przerwany")

# 5. po przerwaniu: ucieczka z ognia działa jak dotąd (stojąc na ogniu bot schodzi)
s, b = scena(); idz(b, s)
s.t += 0.5; s.poz[0], s.poz[1] = 32497, 32300
b.ogien_hp_hist = [(s.t - 1.0, 100.0), (s.t, 92.0)]
b.ogien_pola[H] = s.t
b._marsz_og_pilnuj(tuple(s.poz) + (Z,), s.t)
r = b._ogien_wyjdz(tuple(s.poz) + (Z,), s.t)
sprawdz("5a po przerwaniu zwykła ucieczka z ognia nadal schodzi z pola", r is True and bool(s.kroki), s.kroki)

# 6. limit prób: 2 na 5 min
s, b = scena(); idz(b, s)
b._marsz_og_koniec(START, "test", escape=False)
s.t += 10.0; b.skos_zle[((32498, 32300), (32497, 32299))] = s.t + 30.0
idz(b, s)
sprawdz("6a druga próba dozwolona", len(b.marsz_og_proby) == 2 and b.marsz_og is not None, b.marsz_og_proby)
b._marsz_og_koniec(START, "test", escape=False)
s.t += 10.0; s.kliki.clear()
idz(b, s)
sprawdz("6b trzecia w 5 min: bez kliku, zwykła ścieżka", b.marsz_og is None and not s.kliki and len(b.marsz_og_proby) == 2, s.kliki)
s.t += cavebot.MARSZ_ZA_OGNIEM_OKNO_S; s.poz[0], s.poz[1] = 32498, 32300     # (zwykła ścieżka z 6b ruszyła atrapę)
b.skos_zle[((32498, 32300), (32497, 32299))] = s.t + 30.0
idz(b, s)
sprawdz("6c po 5 min próby znów dostępne", b.marsz_og is not None, b.marsz_og_proby)

# 7. twarde warunki celu i prostokąta
s, b = scena(pola=[(32497, 32301, Z)])            # dodatkowy ogień z ekranu (bez hp:true) w prostokącie
idz(b, s)
sprawdz("7a w prostokącie oprócz znanego ognia także ogień z ekranu bez hp: nie klika", b.marsz_og is None and not s.kliki, s.kliki)
s, b = scena()
b._straznik = (None, types.SimpleNamespace(aktywna=lambda: True, ep={"cel": (32496, 32299, Z)}))     # cel orbity tuż przy ogniu
idz(b, s)
sprawdz("7b cel przy ogniu (Chebyshev 1) nie jest klikany", b.marsz_og is None and not s.kliki, s.kliki)
s, b = scena()
b.ostatnie_stwory = [{"x": 32495, "y": 32298, "z": Z, "hp": 100, "nazwa": "Troll", "id": 5}]
idz(b, s)
sprawdz("7c cel zajęty przez stwora: nie klika w niego (wybiera dalszy/inny albo nic)", not s.kliki or s.kliki[-1] != (-3, -2), s.kliki)
s, b = scena(); s.poz[0], s.poz[1] = 32497, 32300
b.ogien_pola[(32497, 32300, Z)] = s.t
r = b._marsz_za_ogniem((32497, 32300, Z), s.t)
sprawdz("7d postać stojąca na polu ognia: nie startuje (to robi _ogien_wyjdz)", r is None and b.marsz_og is None)

# 8. integracja: monitor w tick i hak w idz_do
zrodlo = open(cavebot.__file__, encoding="utf-8").read()
i = zrodlo.index("self._ogien_tick(poz, teraz)\n        if self.marsz_og is not None:")
sprawdz("8a tick pilnuje marszu za ogniem zaraz po _ogien_tick, przed _ogien_wyjdz", "_marsz_og_pilnuj(poz, teraz)" in zrodlo[i:i + 400]
        and zrodlo.index("_ogien_wyjdz(poz, teraz)", i) > i)
sprawdz("8b pokrętło w pokretla.py: zakres 0-1, analityk nie włączy", __import__("pokretla").ZAKRESY.get("MARSZ_ZA_OGNIEM_ORBITA") == (0, 1)
        and __import__("pokretla").waliduj({"MARSZ_ZA_OGNIEM_ORBITA": 1}, {"MARSZ_ZA_OGNIEM_ORBITA": 0})[0] == {})
sprawdz("8c w na_zywo.przyklad.json domyślnie 0", '"MARSZ_ZA_OGNIEM_ORBITA": 0' in open(_os.path.join(_katalog, "na_zywo.przyklad.json")).read())

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
