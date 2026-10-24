#!/usr/bin/env python3
"""23.10 zgon odchyda (lvl 8, 185 HP, thais_pn_z8 -> z9, 15:49:33-15:50:12): po upadku w dziurę (32354,32131,8) postać stała w zamkniętej kieszeni
na z9 (x 32353..32357, y 32130..32132), Skorpion (spoza --potwory, więc nigdy nieatakowany) stał na polu liny (32354,32131,9), HP 83 -> 0 w ~25 s.
Bot: lina 2x bez skutku (2. próba, gdy Skorpion stał na polu liny), potem UCIECZKA (HP 42% <= próg) wyprzedziła WPADNIECIE: kroki w stronę punktu
trasy z8 (32355,32139) z z9, bez 3. próby liny, bez planu, bez walki, bez leczenia.
Poprawka: gdy wpadnięcie w toku i z tego piętra nie ma drogi do trasy (st['osiag'] fałsz), UCIECZKA nie przejmuje obiegu (WPADNIECIE_UCIECZKA=1):
(a) stwór NA polu liny (albo, po wyczerpaniu prób liny, w odl. <= 2) jest celem mimo --potwory (WPADNIECIE_BIJ=1), (b) lina nie jest zużywana na polu zajętym
przez stwora, (c) lina próbowana od razu, (d) exura także poniżej progu ucieczki. Prawdziwa mapa (mapa.py) i prawdziwe pozycje; atrapy, bez gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import mapa as _mapa
import powiadom
import wpadniecie

for _n, _v in (("WPADNIECIE_UCIECZKA", 1), ("WPADNIECIE_BIJ", 1), ("WPADNIECIE_DRABINA", 1)):
    if not hasattr(cavebot, _n):          # stary kod (bez poprawki): test ma się wysypać na asercjach, nie na braku stałych
        setattr(cavebot, _n, _v)
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
powiadom.powiadom = lambda *a, **k: None
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


M = _mapa.Mapa()
Z8_GRACZ = (32355, 32131, 8)
DZIURA = (32354, 32131, 8)
SPOT = (32354, 32131, 9)           # lądowanie = rope spot
KIESZEN = (32354, 32132, 9)        # tu stał odchyd po zejściu z pola liny
PUNKT_TRASY = (32355, 32139, 8)    # punkt, w stronę którego szły kroki UCIECZKI (log: "krok Down ... cel kroku (32355, 32139)")
sprawdz("0 mapa: dziura z8 flagi 5 (ściana wg mapy), lądowanie z9 chodliwe",
        M.flagi(*DZIURA) & 4 and M.flagi(*SPOT) & 1, f"{M.flagi(*DZIURA)} {M.flagi(*SPOT)}")


class Swiat:
    def __init__(s, hp=77, mana=13, skorpion="spot", drabina=False):
        s.drabina = drabina; s.uzyte = []
        s.t = 0.0; s.poz = list(Z8_GRACZ); s.hp = hp; s.mana = mana
        s.klawisze = []; s.liny = []; s.ataki = []
        s.skorpion = skorpion
        s.sk = {"id": 88, "nazwa": "Scorpion", "gracz": False, "z": 9, "hp": 100}

    def zegar(s): return s.t
    def spij(s, d): s.t += d

    def zapytaj(s, z):
        s.t += 0.02
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 185, "mana": s.mana, "max_mana": 35, "proc": 100.0 * s.hp / 185}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            l = [ja]
            if s.poz[2] == 9 and s.skorpion:
                x, y = (SPOT[0], SPOT[1]) if s.skorpion == "spot" else (SPOT[0] + 3, SPOT[1] + 1)
                l.append(dict(s.sk, x=x, y=y))
            return {"stwory": l}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k): p.s.klawisze.append(k); return False


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz):
        o.s.uzyte.append((tuple(pole), tuple(poz)))
        if o.s.drabina and tuple(pole) == SPOT:          # drabina: Use na polu (x, y, z9) = lądowanie (x, y+1, z8)
            o.s.poz[:] = [SPOT[0], SPOT[1] + 1, 8]
    def uzyj_line(o, pole, poz): o.s.liny.append(tuple(pole))


def nowy(s, zdrowie=0, uciekanie=1, bij=1):
    LOG.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    cavebot.WPADNIECIE_UCIECZKA = uciekanie
    cavebot.WPADNIECIE_BIJ = bij
    cavebot.ZDROWIE_CZAR_AKTYWNY = zdrowie
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    trasa = [(32355, 32135, 8), PUNKT_TRASY, (32356, 32139, 8)]
    b = cavebot.Cavebot(P(s), trasa, zapytaj=s.zapytaj, atak=lambda m, g: s.ataki.append((m["nazwa"], m["x"], m["y"])),
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, potwory=["troll", "rat"])
    b.przerwa_od = float("inf"); b.prog_aktualny = 45.0
    b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        kopia = kat / "na_zywo.json"; kopia.write_text("{}"); b.pokretla.plik = kopia
    w = b._wp(); w.plik_stop = kat / "STOP"
    b.idx = 2                                  # stoimy za punktem (32355,32135,8); cel UCIECZKI = punkty[1] = PUNKT_TRASY (z8)
    return b


def upadek(s, b):
    """Obieg na z8 (próbka obserwuj), potem postać stoi na z9 w (32354,32131) i schodzi na pole obok (kieszeń)."""
    b.tick()
    s.poz[:] = list(SPOT)
    b.tick()                                    # wykrycie: "Wpadłem"
    s.poz[:] = list(KIESZEN)
    st = b.wpadniecie.st
    if st is not None:
        st["lina"] = 0; st["uzyj"] = 0            # próby z ticka wykrycia (Use/lina z pola lądowania) nie liczą się; Use z pola lądowania (tick wykrycia) nie liczy się do scenariuszy z kieszeni
        st["lina_zszedl"] = True                # postać już zeszła z pola liny (jak w logu 15:49:34)
        st["nast"] = 0.0


def czysc(s):
    s.klawisze.clear(); s.liny.clear(); s.ataki.clear(); s.uzyte.clear(); LOG.clear()


# --- A. Skorpion stoi NA polu liny, HP 77/185 = 41,6% (<= próg 45): UCIECZKA nie wolno wyprzedzić wpadnięcia ---
s = Swiat(hp=77, skorpion="spot"); b = nowy(s)
upadek(s, b)
sprawdz("A0 wykryte wpadnięcie z8 <- z9, pole liny = lądowanie",
        b.wpadniecie.st is not None and b.wpadniecie.st["z0"] == 8 and b.wpadniecie.st["z1"] == 9
        and tuple(b.wpadniecie.st["lad"]) == SPOT, b.wpadniecie.st)
czysc(s)
for _ in range(3):
    b.tick()
sprawdz("A1 stan NIE jest UCIECZKA (kroki do punktu trasy z innego piętra)", "UCIECZKA" not in str(b.stan), b.stan)
sprawdz("A2 żaden krok klawiszem w stronę punktu trasy z8 (Down/Right) z kieszeni", not any(k in ("Down", "Right", "Left", "Up") for k in s.klawisze), s.klawisze)
sprawdz("A3 Skorpion na polu liny jest celem mimo --potwory (walka zamiast kroków)", ("Scorpion", SPOT[0], SPOT[1]) in s.ataki, (s.ataki, LOG[-4:]))
sprawdz("A4 lina nie jest zużywana na polu zajętym przez stwora", s.liny == [], s.liny)

# --- B. Skorpion w kieszeni, ale NIE na polu liny (3 pola dalej): lina od razu, bez walki i bez kroków ---
s = Swiat(hp=77, skorpion="obok"); b = nowy(s)
upadek(s, b)
czysc(s)
for _ in range(8):
    b.tick()
sprawdz("B1 lina pierwsza, na polu lądowania (32354,32131,9)", SPOT in s.liny, (s.liny, LOG[-5:]))
sprawdz("B2 bez kroków ucieczki", not s.klawisze, s.klawisze)
sprawdz("B3 Skorpion 3 pola od nas przy wolnej linie nie jest bity (lina pierwsza)", s.ataki == [], s.ataki)

# --- C. Po wyczerpaniu prób liny Skorpion w odl. <= 2 jest celem; dalszy (3+) nie ---
s = Swiat(hp=140, skorpion="obok"); b = nowy(s)
upadek(s, b)
b.wpadniecie.st["lina"] = 3; b.wpadniecie.st["uzyj"] = 2
czysc(s)
sk_blisko = dict(s.sk, x=KIESZEN[0] + 1, y=KIESZEN[1])
sk_daleko = dict(s.sk, x=KIESZEN[0] + 3, y=KIESZEN[1])
sprawdz("C1 po wyczerpaniu liny: Skorpion w odl. 1 jest kandydatem", b.kandydaci([sk_blisko], KIESZEN) == [sk_blisko])
sprawdz("C2 po wyczerpaniu liny: Skorpion w odl. 3 nie jest kandydatem", b.kandydaci([sk_daleko], KIESZEN) == [])
b.wpadniecie.st["lina"] = 0
sprawdz("C3 przy wolnej linie Skorpion w odl. 1 (nie na polu liny) nie jest kandydatem", b.kandydaci([sk_blisko], KIESZEN) == [])
sprawdz("C4 poza wpadnięciem Skorpion spoza --potwory nadal nie jest kandydatem",
        (setattr(b.wpadniecie, "st", None) or b.kandydaci([sk_blisko], KIESZEN)) == [])

# --- F. KOREKTA KAROLA 23.10: to była DRABINA (32354,32131,9), nie lina. Postać w kieszeni (32354,32132,9), Skorpion obok/na polu:
#        Use na drabinie w ciągu kilku sekund, wejście na (32354,32132,8) ---
for _gdzie in ("spot", "obok"):
    s = Swiat(hp=77, skorpion=_gdzie, drabina=True); b = nowy(s)
    upadek(s, b)
    czysc(s)
    t0 = s.t
    for _ in range(10):
        b.tick()
        if s.poz[2] == 8:
            break
    sprawdz(f"F1 drabina, Skorpion {_gdzie}: Use na polu drabiny (32354,32131,9)", any(u[0] == SPOT for u in s.uzyte), (s.uzyte, LOG[-4:]))
    sprawdz(f"F2 drabina, Skorpion {_gdzie}: postać na z8 w (32354,32132) w < 8 s (jedna lina + Use)", tuple(s.poz) == (SPOT[0], SPOT[1] + 1, 8) and s.t - t0 < 8.0, (s.poz, round(s.t - t0, 1)))
    sprawdz(f"F3 drabina, Skorpion {_gdzie}: najwyżej jedna lina (na zajętym polu żadna), bez kroków ucieczki", len(s.liny) <= (0 if _gdzie == "spot" else 1) and not any(k in ("Down", "Right", "Left", "Up") for k in s.klawisze), (s.liny, s.klawisze))
# F4: Use od razu na własnym polu lądowania (zanim postać zejdzie z niego), drabina pod nogami
s = Swiat(hp=140, skorpion=None, drabina=True); b = nowy(s)
b._wp().drabiny.add(SPOT)                       # pole nauczone jako drabina (np. z drabiny_nauczone.json)
b.tick(); s.poz[:] = list(SPOT); b.tick()
sprawdz("F4 znana drabina: po upadku Use od razu na własnym polu lądowania", s.uzyte[:1] == [(SPOT, SPOT)] and s.poz[2] == 8, (s.uzyte, s.poz))
# F5: lina zawiodła 1x -> drugi Use przed drugą liną
s = Swiat(hp=140, skorpion=None, drabina=False); b = nowy(s)
upadek(s, b)
czysc(s)
for _ in range(40):
    b.tick()
sprawdz("F5 bez drabiny: lina, Use, lina, Use, lina (Use między linami)", len(s.uzyte) == 2 and len(s.liny) == 3, (s.uzyte, s.liny))

# --- D. WPADNIECIE_UCIECZKA=0: dawne zachowanie (UCIECZKA wyprzedza wpadnięcie) - dowód, że test A coś mierzy ---
s = Swiat(hp=77, skorpion="spot"); b = nowy(s, uciekanie=0)
upadek(s, b)
czysc(s)
for _ in range(3):
    b.tick()
sprawdz("D1 WPADNIECIE_UCIECZKA=0: UCIECZKA przejmuje obieg jak dotąd", "UCIECZKA" in str(b.stan) or any(k in ("Down", "Right", "Left", "Up") for k in s.klawisze), (b.stan, s.klawisze))

# --- E. Leczenie: exura poniżej progu ucieczki, gdy wpadnięcie bez drogi (mana 30 >= 25) ---
s = Swiat(hp=60, mana=30, skorpion="obok"); b = nowy(s, zdrowie=1)
b.zd_wylaczony_do = 0.0
upadek(s, b)
b.wpadniecie.st["lina"] = 3                      # lina wyczerpana, zostaje leczenie i walka
b.zd_oczekuje = None; b.czar_ostatni = float("-inf")     # rzut z ticka wykrycia nie liczy się
czysc(s)
b.tick()
sprawdz("E1 HP 32% (<= próg 45), wpadnięcie bez drogi, mana 30: exura (F2)", "F2" in s.klawisze, (s.klawisze, LOG[-4:]))
s = Swiat(hp=60, mana=30, skorpion="obok"); b = nowy(s, zdrowie=1, uciekanie=0)
upadek(s, b)
b.wpadniecie.st["lina"] = 3
b.zd_oczekuje = None; b.czar_ostatni = float("-inf")
czysc(s)
b.tick()
sprawdz("E2 WPADNIECIE_UCIECZKA=0: jak dotąd bez exury poniżej progu", "F2" not in s.klawisze, s.klawisze)
s = Swiat(hp=60, mana=10, skorpion="obok"); b = nowy(s, zdrowie=1)
upadek(s, b)
b.wpadniecie.st["lina"] = 3
b.zd_oczekuje = None; b.czar_ostatni = float("-inf")
czysc(s)
b.tick()
sprawdz("E3 mana 10 < 25: bez exury (brak many nie wywołuje spamu)", "F2" not in s.klawisze, s.klawisze)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
