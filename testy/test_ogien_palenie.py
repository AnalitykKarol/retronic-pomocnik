"""27.10 reguła Karola: ogień zadaje obrażenia w czasie (do ok. 2 min po kontakcie), a polu przypisujemy tylko PIERWSZE obrażenie. Okno palenia
OGIEN_PODPALENIE_S (domyślnie 120 s) po pierwszym przypisanym obrażeniu: dalsze spadki HP NIE oznaczają kolejnych pól jako parzących (tylko atrybucja do
epizodów/maski; ucieczka z ognia i unikanie znanych pól bez zmian). Offline, na atrapach (RETRONIC_TESTY=1), wzór test_wydra_ogien.py."""
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



A = (32498, 32301, Z)       # pierwsze pole z ogniem (nieznane)
B = (32499, 32302, Z)       # drugie nieznane pole z ogniem
C = (32499, 32303, Z)       # trzecie

def klucz(p): return f"{p[0]},{p[1]},{p[2]}"
def hp_pola(b, p): return b.ogien_epizody.get(klucz(p), {}).get("hp")

# 1. domyślne okno palenia
sprawdz("1a okno palenia domyślnie 120 s", cavebot.OGIEN_PODPALENIE_S == 120.0, cavebot.OGIEN_PODPALENIE_S)

# 2. pierwsze obrażenie oznacza pole, drugi spadek HP w oknie nie oznacza następnego
s, b = zrob(A, {})
tick(b, s, A, 1.0, {(0, 0)}, hp=(100.0, 92.0))
t1 = s.t
sprawdz("2a pierwsze obrażenie oznacza pole A jako parzące", hp_pola(b, A) is True, b.ogien_epizody.get(klucz(A)))
sprawdz("2b okno palenia otwarte na OGIEN_PODPALENIE_S od pierwszego obrażenia", abs(b.ogien_podpalony_do - (t1 + cavebot.OGIEN_PODPALENIE_S)) < 0.01,
        (b.ogien_podpalony_do, t1))
tick(b, s, B, 30.0, {(0, 0)}, hp=(92.0, 86.0))        # 30 s później: kolejny tik TEGO SAMEGO palenia, postać na innym polu z ogniem
sprawdz("2c drugi spadek HP w oknie NIE oznacza pola B", hp_pola(b, B) is False, b.ogien_epizody.get(klucz(B)))
tick(b, s, C, 60.0, {(0, 0)}, hp=(86.0, 80.0))        # 91 s po pierwszym: nadal w oknie 120 s (przy dawnych 60 s byłoby oznaczone)
sprawdz("2d 91 s po pierwszym obrażeniu nadal w oknie: pole C nie oznaczone", hp_pola(b, C) is False, (s.t - t1, b.ogien_epizody.get(klucz(C))))
sprawdz("2e znane pole A zostaje parzące (unikanie znanych pól bez zmian)", (A[0], A[1]) in b._ogien_parzy_dane(Z))

# 3. po oknie znów oznacza (brzegi: 119 s w oknie, 121 s po oknie)
def po_pierwszym(dt):
    s, b = zrob(A, {})
    tick(b, s, A, 1.0, {(0, 0)}, hp=(100.0, 92.0))
    tick(b, s, B, dt, {(0, 0)}, hp=(92.0, 86.0))
    return b
sprawdz("3a 119 s po pierwszym: w oknie, pole B nie oznaczone", hp_pola(po_pierwszym(119.0), B) is False)
sprawdz("3b 121 s po pierwszym: po oknie, pole B oznaczone", hp_pola(po_pierwszym(121.0), B) is True)
s, b = zrob(A, {})
tick(b, s, A, 1.0, {(0, 0)}, hp=(100.0, 92.0))
tick(b, s, B, 150.0, {(0, 0)}, hp=(92.0, 86.0))
sprawdz("3c po oknie nauka działa jak dawniej: B hp, nowe okno", hp_pola(b, B) is True and b.ogien_podpalony_do > s.t)

# 4. ochrona życia bez zmian: w oknie spadek HP nadal potwierdza ogień i zejście z pola (ucieczka)
s, b = zrob(A, {})
tick(b, s, A, 1.0, {(0, 0)}, hp=(100.0, 92.0))
s.t += 20.0; s.poz[0], s.poz[1] = B[0], B[1]
b.ogien_pola[B] = s.t
b.ogien_hp_hist = [(s.t - 1.0, 92.0), (s.t, 86.0)]
r = b._ogien_wyjdz(B, s.t)
sprawdz("4a w oknie palenia stojąc na polu ognia po spadku HP bot nadal schodzi (ucieczka bez zmian)", r is True and bool(s.kroki), s.kroki)
sprawdz("4b ... a pole B nie jest oznaczone", hp_pola(b, B) is not True)

# 5. wejście na znane parzące pole otwiera okno na OGIEN_PODPALENIE_S (120 s)
s, b = zrob((32497, 32300), {"32497,32300,8": {"n": 52, "godz": [8, 9], "hp": True, "ost": 0.0}})
tick(b, s, (32497, 32300, Z), 1.0, {(0, 0)})
sprawdz("5a wejście na znane parzące pole: okno 120 s", abs(b.ogien_podpalony_do - (s.t + 120.0)) < 0.01, (b.ogien_podpalony_do, s.t))

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
