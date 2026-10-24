"""24.10 odchyd, zasypana dziura (32663,31962,z7) pod Kazordoonem. Dwa błędy z logów mozg-stdout-1024-1031/1045:
(a) pietra.py: po udanym Use łopaty krok w dziurę szedł dopiero po odstępie (ok. 2 s) i przesunięcie po łopacie (walka z wężami,
    postać 2 pola od pola) kończyło się „nie zbliżam się do pola … zmieniam kandydata” -> „wyczerpane pola przejścia”,
    bo st["postep"] zostawał ze starym czasem (czekanie na HP/walka) i stałym d=2;
(b) cavebot.CavebotDojscie._idz_trasa: dojście 4-punktowe ze startem w miejscu postaci; _dojscie_sync ustawiał idx=1, a podgląd
    „punkty już osiągnięte” szedł z zawinięciem (k=(idx+dalej)%n) i uznawał punkt 0 (= pozycja) za zaliczony z przebiegnięciem
    całej trasy -> „Okrążenie 1 gotowe” -> „koniec trasy bez osiągnięcia celu” x5 w kilka sekund.
Atrapy jak w test_lopata_pamiec.py (prawdziwa mapa, dziura zasypana do użycia łopaty z pola obok)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wypad, pietra
from pathlib import Path

LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
T = (32663, 31962, 7)
DOL = (32663, 31962, 8)


class Swiat:
    """Dziura T zasypana do użycia łopaty z sąsiedniego pola; potem otwarta przez `otwarta_s` sekund (None = na stałe)."""
    def __init__(s, poz, otwarta_s=None, popchniecie=None, hp=100):
        s.t = 0.0; s.poz = list(poz); s.zmiany = []; s.kopal = []; s.otwarta_do = None; s.otwarta_s = otwarta_s
        s.popchniecie = popchniecie; s.t_kopania = None; s.t_zmiany = None; s.hp = hp; s.kroki = []
        s.potwory = []; s.po_lopacie = None; s.hp_wraca = None      # po_lopacie: {"stwory": [...], "hp": int} ustawiane przy Use łopaty
    def zegar(s): return s.t
    def klik(s, dx, dy): pass
    def spij(s, d): s.t += d
    def otwarta(s):
        return s.otwarta_do is not None and s.t <= s.otwarta_do
    def zapytaj(s, z):
        s.t += 0.05
        if s.hp_wraca is not None and s.t >= s.hp_wraca[0]:
            s.hp = s.hp_wraca[1]; s.hp_wraca = None
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": s.hp}] + list(s.potwory)}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        if (x, y, z) == T:
            s.kroki.append((round(s.t, 2), "T", s.otwarta()))
            if s.otwarta():
                s.zmiany.append((tuple(s.poz), 8)); s.t_zmiany = s.t; s.poz[:] = [x, y, 8]; return
            s.poz[0], s.poz[1] = x, y; return              # zasypana (albo już zamknięta): stoi na niej, nie spada
        v = M.flagi(x, y, z)
        if not v & 1 or v & 4:
            return
        if v & 2 and z != 7:
            return
        s.poz[0], s.poz[1] = x, y


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): pass
    def uzyj_line(o, pole, poz): pass
    def uzyj_lopate(o, cel, poz):
        s = o.s
        s.kopal.append((tuple(cel), tuple(poz), round(s.t, 2)))
        if tuple(cel) == T and max(abs(cel[0] - poz[0]), abs(cel[1] - poz[1])) == 1:
            s.t_kopania = s.t
            s.otwarta_do = float("inf") if s.otwarta_s is None else s.t + s.otwarta_s
            if s.po_lopacie is not None:                # w trakcie łopaty (kilka sekund) pojawił się potwór i/lub spadło HP
                s.potwory = list(s.po_lopacie.get("stwory", [])); s.hp = s.po_lopacie.get("hp", s.hp)
            if s.popchniecie is not None:               # walka: wąż/troll odepchnął nas, mijają sekundy
                s.t += s.popchniecie[1]; s.poz[:] = list(s.popchniecie[0]); s.popchniecie = None


TRASA = [(32663, 31960, 7), (32663, 31961, 7), T, DOL, (32663, 31963, 8)]


def nowy(start, otwarta_s=None, popchniecie=None, hp=100, idx=2, dojscie=False, po_lopacie=None):
    """Świat + Cavebot na trasie TRASA (dziura T zasypana). dojscie=True: dojscie_aktywne (włącza bramkę HP_PRZED_PIETREM)."""
    LOG.clear()
    wypad.PLIK_PRZEJSC = _os.path.join(tempfile.mkdtemp(), "p.json")
    s = Swiat(start, otwarta_s, popchniecie, hp)
    s.po_lopacie = po_lopacie
    b = cavebot.Cavebot(P(s), TRASA + [TRASA[-1]] * 10, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=M,
                        klik=s.klik, okrazenia=1)
    b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        try:
            d = json.loads((Path(_R) / "na_zywo.json").read_text())
        except Exception:
            d = {}
        d.update({"PIETRA_TRYBY_Z_DANYCH": 1, "PRZEJSCIE_TRZY_SPOSOBY": 1, "PIETRA_LOPATA": 1})
        kopia = Path(tempfile.mkdtemp()) / "na_zywo.json"; kopia.write_text(json.dumps(d))
        b.pokretla.plik = kopia
    cavebot.PRZEJSCIE_TRZY_SPOSOBY = 1; cavebot.PIETRA_TRYBY_Z_DANYCH = 1
    b.idx = idx
    if dojscie:
        b.dojscie_aktywne = True
    return s, b


def bieg(start, otwarta_s=None, popchniecie=None, hp=100, idx=2, ticki=200, dojscie=False, po_lopacie=None, do_lopaty=False):
    """do_lopaty=True: kończy zaraz po obiegu, w którym padło Use łopaty (do oceny „w tym samym obiegu”)."""
    stare = pietra.ZASYPANE
    pietra.ZASYPANE = {T}
    try:
        s, b = nowy(start, otwarta_s, popchniecie, hp, idx, dojscie, po_lopacie)
        for _ in range(ticki):
            if s.zmiany or not b.tick() or (do_lopaty and s.kopal):
                break
        return s, b
    finally:
        pietra.ZASYPANE = stare


# 1. spokój (jak 10:48): łopata z pola obok i krok w dziurę w TYM SAMYM przejściu, zanim dziura się zamknie (otwarta 1,5 s)
s, b = bieg((32663, 31961, 7), otwarta_s=1.5)
sprawdz("1 zejście na z8 mimo dziury otwartej tylko 1,5 s", s.poz[2] == 8 and s.poz[:2] == [32663, 31962], f"{s.poz} {s.kopal} {s.kroki}")
sprawdz("1 krok w dziurę zaraz po łopacie (<= 1,2 s od Use)", s.t_zmiany is not None and s.t_kopania is not None
        and s.t_zmiany - s.t_kopania <= 1.2, f"kopanie {s.t_kopania} zmiana {s.t_zmiany}")
sprawdz("1 łopata raz", len(s.kopal) == 1, f"{s.kopal}")
sprawdz("1 pamięć = lopata", wypad.przejscia_nauczone(wypad.PLIK_PRZEJSC).get("32663,31962,7>8", {}).get("tryb") == "lopata",
        f"{wypad.przejscia_nauczone(wypad.PLIK_PRZEJSC)}")

# 2. po łopacie walka odsuwa postać o 2 pola i mija 30 s (10:43:39-48): wracamy i wchodzimy, nie „wyczerpane pola przejścia”
s, b = bieg((32663, 31964, 7), popchniecie=((32663, 31964, 7), 30.0), idx=3)   # idx=3: przejście pięter od razu z odl 2 (postep[1]=2)
sprawdz("2 po przesunięciu o 2 pola i 30 s: zejście na z8", s.poz[2] == 8 and s.poz[:2] == [32663, 31962], f"{s.poz} {s.kopal} {s.kroki}")
sprawdz("2 bez „zmieniam kandydata” i bez porażki", not any("zmieniam kandydata" in l or "NIEUDANE" in l for l in LOG),
        [l for l in LOG if "Przejście" in l][-4:])
sprawdz("2 łopata raz (dziura nadal otwarta, nie kopiemy drugi raz)", len(s.kopal) == 1, f"{s.kopal}")

# 3. HP poniżej progu (bezpieczeństwo): bramka cb._hp_przed_pietrem puszcza do chwili Use łopaty, a potem trzyma 15 s:
#    krok w dziurę zaraz po łopacie MUSI przejść przez bramkę (nie wolno go wykonać „obok” niej)
bramka = []
LOG.clear()
wypad.PLIK_PRZEJSC = _os.path.join(tempfile.mkdtemp(), "p.json")
pietra.ZASYPANE = {T}
try:
    s = Swiat((32663, 31961, 7))
    def hp_bramka(poz, teraz, klucz):
        bramka.append(round(teraz, 2))
        return s.t_kopania is not None and teraz < s.t_kopania + 15.0
    b = cavebot.Cavebot(P(s), TRASA + [TRASA[-1]] * 10, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=M, klik=s.klik, okrazenia=1)
    b.pietra_ops = Ops(s); b._hp_przed_pietrem = hp_bramka
    if b.pokretla is not None:
        d = json.loads((Path(_R) / "na_zywo.json").read_text()); d.update({"PIETRA_TRYBY_Z_DANYCH": 1, "PRZEJSCIE_TRZY_SPOSOBY": 1, "PIETRA_LOPATA": 1})
        kopia = Path(tempfile.mkdtemp()) / "na_zywo.json"; kopia.write_text(json.dumps(d)); b.pokretla.plik = kopia
    cavebot.PRZEJSCIE_TRZY_SPOSOBY = 1; cavebot.PIETRA_TRYBY_Z_DANYCH = 1
    b.idx = 2
    for _ in range(400):
        if s.zmiany or not b.tick():
            break
finally:
    pietra.ZASYPANE = {(32493, 32259, 7), (32347, 32123, 7), (32663, 31962, 7)}
sprawdz("3 wejście w dziurę dopiero po puszczeniu bramki HP (>= 15 s po łopacie)", s.t_zmiany is not None and s.t_kopania is not None
        and s.t_zmiany >= s.t_kopania + 15.0 and s.poz[2] == 8, f"kopanie {s.t_kopania} zmiana {s.t_zmiany} {s.kroki}")
sprawdz("3 krok na T nie wyprzedził bramki (żaden krok na T w oknie 15 s po łopacie)", s.t_kopania is not None
        and not any(s.t_kopania < k[0] < s.t_kopania + 15.0 for k in s.kroki), f"{s.kroki}")

# 4. zwykłe przejścia bez zmian: dziura nie zasypana (poza ZASYPANE, bez pamięci, AUTO=0): krok w otwartą dziurę, bez łopaty
LOG.clear()
wypad.PLIK_PRZEJSC = _os.path.join(tempfile.mkdtemp(), "p.json")
pietra.ZASYPANE = set()
try:
    s = Swiat((32663, 31961, 7)); s.otwarta_do = float("inf")
    b = cavebot.Cavebot(P(s), TRASA + [TRASA[-1]] * 10, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=M, klik=s.klik, okrazenia=1)
    b.pietra_ops = Ops(s)
    cavebot.PRZEJSCIE_TRZY_SPOSOBY = 1; cavebot.PIETRA_TRYBY_Z_DANYCH = 1
    b.idx = 2
    for _ in range(100):
        if s.zmiany or not b.tick():
            break
finally:
    pietra.ZASYPANE = {(32493, 32259, 7), (32347, 32123, 7), (32663, 31962, 7)}
sprawdz("4 otwarta dziura: krok i z8 bez łopaty", s.poz[2] == 8 and not s.kopal, f"{s.poz} {s.kopal}")

# 7. pokrętło PIETRA_LOPATA_WEJSCIE=0 przywraca dawne zachowanie (brak natychmiastowego kroku: dziura otwarta 1,5 s zamyka się przed krokiem)
cavebot.PIETRA_LOPATA_WEJSCIE = 0
try:
    s, b = bieg((32663, 31961, 7), otwarta_s=1.5)
finally:
    cavebot.PIETRA_LOPATA_WEJSCIE = 1
sprawdz("7 pokrętło 0: dawna ścieżka (bez natychmiastowego kroku)", s.poz[2] == 7 and not any("od razu krok" in l for l in LOG), f"{s.poz}")
import pokretla
sprawdz("7 pokrętła w ZAKRESY, przykładzie i cavebot", all(k in pokretla.ZAKRESY for k in ("PIETRA_LOPATA_WEJSCIE", "PIETRA_LOPATA_OKNO_S"))
        and all(k in json.load(open(_R + "/na_zywo.przyklad.json")) for k in ("PIETRA_LOPATA_WEJSCIE", "PIETRA_LOPATA_OKNO_S"))
        and cavebot.PIETRA_LOPATA_WEJSCIE == 1 and cavebot.PIETRA_LOPATA_OKNO_S == 90.0)

# 5. dojście 4-punktowe od pozycji 2 pola od celu na innym piętrze (10:45): bez „Okrążenie gotowe”, bez porażki, z przejściem
def dojscie(start, punkty, otwarta=True, tol=2):
    LOG.clear()
    wypad.PLIK_PRZEJSC = _os.path.join(tempfile.mkdtemp(), "p.json")
    s = Swiat(start)
    if otwarta:
        s.otwarta_do = float("inf")
    d = cavebot.CavebotDojscie(P(s), punkty, 1, None, 40, None, None, True, zapytaj=s.zapytaj, atak=lambda m, g: None,
                               alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=None, mapa=M, klik=s.klik, tolerancja=tol)
    d.pietra_ops = Ops(s)
    cavebot.PRZEJSCIE_TRZY_SPOSOBY = 1; cavebot.PIETRA_TRYBY_Z_DANYCH = 1
    for _ in range(120):
        if not d.tick():
            break
    return s, d

PKT4 = [(32663, 31964, 7), (32663, 31963, 7), (32663, 31962, 7), DOL]
s, d = dojscie((32663, 31964, 7), PKT4)
sprawdz("5 dojście 4 pkt z 2 pól od celu: bez „Okrążenie gotowe” / „koniec trasy”", not any("Okrążenie" in l or "koniec trasy" in l for l in LOG), LOG[-6:])
sprawdz("5 dojście 4 pkt: bez porażki, cel osiągnięty na z8", not d.dojscie_porazka and d.dojscie_ok and s.poz[2] == 8, f"{s.poz} ok={d.dojscie_ok} por={d.dojscie_porazka} {LOG[-4:]}")

# 6. start na punkcie 0 dłuższej (11 pkt, jak 10:48) trasy dojścia i krótka trasa 3-punktowa: cel osiągnięty, bez fałszywego końca
PKT11 = [(x, 31961, 7) for x in range(32671, 32662, -1)] + [T, DOL]
s, d = dojscie((32671, 31961, 7), PKT11)
sprawdz("6a dojście 11 pkt od punktu 0: cel osiągnięty na z8", d.dojscie_ok and not d.dojscie_porazka and s.poz[2] == 8, f"{s.poz} {LOG[-4:]}")
PKT3 = [(32663, 31961, 7), T, DOL]
s, d = dojscie((32663, 31961, 7), PKT3)
sprawdz("6b dojście 3 pkt od punktu 0: cel osiągnięty", d.dojscie_ok and not d.dojscie_porazka and s.poz[2] == 8, f"{s.poz} {LOG[-4:]}")
# 6c. przejście naprawdę niemożliwe (dziura zasypana, poza ZASYPANE i bez pamięci łopaty) nadal kończy porażką, nie wisi
pietra.ZASYPANE = set()
try:
    s, d = dojscie((32663, 31961, 7), PKT3, otwarta=False)
finally:
    pietra.ZASYPANE = {(32493, 32259, 7), (32347, 32123, 7), (32663, 31962, 7)}
sprawdz("6c bez możliwości przejścia dojście kończy się porażką (nie nieskończona pętla)", not d.dojscie_ok and s.poz[2] == 7, f"{s.poz} ok={d.dojscie_ok}")

# 8. review 24.10: walka/HP mają pierwszeństwo przed natychmiastowym krokiem w dziurę
START = (32663, 31961, 7)
WAZ = {"id": 7, "nazwa": "Snake", "gracz": False, "x": 32662, "y": 31961, "z": 7, "hp": 100}       # obok postaci kopiącej z (32662,31962)
s, b = bieg(START, po_lopacie={"stwory": [WAZ]}, do_lopaty=True)
def po_lopacie_kroki(s):
    return [k for k in s.kroki if s.t_kopania is not None and k[0] >= s.t_kopania]      # kroki na T po Use łopaty

sprawdz("8a potwór obok po łopacie: łopata padła, w tym samym obiegu BRAK kroku w dziurę",
        len(s.kopal) == 1 and not po_lopacie_kroki(s) and not s.zmiany and not any("od razu krok" in l for l in LOG),
        f"{s.kopal} {s.kroki} {s.poz}")
s.potwory = []                                  # walka skończona: zwykła ścieżka tick() wchodzi w (nadal otwartą) dziurę
for _ in range(100):
    if s.zmiany or not b.tick():
        break
sprawdz("8b po walce zwykły tick() wchodzi w dziurę i bez drugiej łopaty", s.poz[2] == 8 and len(s.kopal) == 1, f"{s.poz} {s.kopal} {s.kroki}")

s, b = bieg(START, po_lopacie={"stwory": [dict(WAZ, x=32660, y=31962)]}, do_lopaty=True)      # dokładnie 2 pola (granica)
sprawdz("8c potwór 2 pola od nas po łopacie: też brak kroku w tym samym obiegu", len(s.kopal) == 1 and not po_lopacie_kroki(s) and not s.zmiany,
        f"{s.kroki} {s.poz}")
s, b = bieg(START, po_lopacie={"stwory": [dict(WAZ, x=32656, y=31962)]}, do_lopaty=True)      # 6 pól: poza strefą, krok jak dawniej
sprawdz("8d potwór daleko (6 pól) po łopacie: w tym samym obiegu krok i zejście jak dawniej", s.poz[2] == 8 and po_lopacie_kroki(s), f"{s.poz} {s.kroki}")

s, b = bieg(START, po_lopacie={"hp": 40}, do_lopaty=True)
sprawdz("9a HP spadło w trakcie łopaty (100 -> 40): w tym samym obiegu BRAK kroku", len(s.kopal) == 1 and not po_lopacie_kroki(s) and not s.zmiany
        and not any("od razu krok" in l for l in LOG), f"{s.kroki} {s.poz}")

# 9b. bramka HP ma czytać ŚWIEŻE HP: start 91% (>= próg 90, bramka puszcza przed łopatą), w trakcie łopaty 89% (spadek 2 pp < 3 pp, więc
#     „gryzie” nie łapie), HP wraca po 12 s: żaden krok na T przed powrotem HP (g_tick z początku obiegu mówiłby 91%)
s, b = nowy(START, hp=91, dojscie=True, po_lopacie={"hp": 89})
pietra.ZASYPANE = {T}
try:
    s.hp_wraca = (12.0, 100)
    for _ in range(400):
        if s.zmiany or not b.tick():
            break
finally:
    pietra.ZASYPANE = {(32493, 32259, 7), (32347, 32123, 7), (32663, 31962, 7)}
sprawdz("9b bramka HP na świeżym HP: brak kroku na T, dopóki HP (89%) < progu; po powrocie HP zejście", s.poz[2] == 8
        and po_lopacie_kroki(s) and all(k[0] >= 12.0 for k in po_lopacie_kroki(s)), f"{s.kroki} kopanie {s.t_kopania} {s.poz}")

# 10. NIT: okno łopaty (lopata_do) przypięte do pola T kandydata i kasowane przy zmianie kandydata
s, b = bieg(START, po_lopacie={"stwory": [WAZ]}, do_lopaty=True)
st = b.pietra.st
sprawdz("10a po łopacie okno przypięte do T", st.get("lopata_T") == T and st.get("lopata_do", 0) > s.t, f"{st.get('lopata_T')} {st.get('lopata_do')}")
inne = (32663, 31970, 7)                        # inny kandydat (daleko): stare okno NIE chroni go przed „nie zbliżam się”
st["postep"] = [s.t - 100.0, cheb_ := max(abs(s.poz[0] - inne[0]), abs(s.poz[1] - inne[1]))]
ki0 = st["ki"]
b.pietra._dojdz(tuple(s.poz), inne, st, s.t)
sprawdz("10b inne pole niż T z oknem łopaty: zmiana kandydata nie jest zablokowana, okno skasowane",
        st["ki"] == ki0 + 1 and "lopata_do" not in st and "lopata_T" not in st, f"ki={st['ki']} {sorted(st)}")
s, b = bieg(START, po_lopacie={"stwory": [WAZ]}, do_lopaty=True)
st = b.pietra.st
st["postep"] = [s.t - 100.0, 2]
t_10c = s.t
b.pietra._dojdz((32663, 31964, 7), T, st, t_10c)
sprawdz("10c to samo pole T w oknie łopaty: kandydat zostaje (postęp odświeżony)", st["ki"] == 0 and st["postep"][0] == t_10c, f"ki={st['ki']} {st['postep']}")

# 11. strażnik postępu dojścia (cavebot.DOJSCIE_BRAK_POSTEPU_S): brak nowego idx przez limit w stanie IDZ = porażka próby;
#     idx do przodu, PAUZA_HP, WYPAD i WALKA zerują odliczanie; atrapa bez zegara nie wywraca ticka
def atrapa(zegar=True):
    d = cavebot.CavebotDojscie.__new__(cavebot.CavebotDojscie)
    d.postac = types.SimpleNamespace(pozycja=lambda: (10, 10, 7))
    d.punkty = [(10, 10, 7), (10, 20, 7), (10, 30, 7), (10, 40, 7), (10, 50, 7), (10, 60, 7), (10, 70, 7)]
    d.idx = 1; d.dojscie_ok = False; d.dojscie_porazka = False; d.dojscie_tol = 2
    d._dojscie_cel = d.punkty[-1]; d._dojscie_prev = 0; d.wypad_aktywny = False
    d.stan = "IDZ"; d.zeg = types.SimpleNamespace(t=0.0)
    if zegar:
        d.zegar = lambda: d.zeg.t
    return d

_tick0 = cavebot.Cavebot.tick; _log0 = cavebot.log
cavebot.Cavebot.tick = lambda self: "super"; cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
_lim0 = cavebot.DOJSCIE_BRAK_POSTEPU_S
cavebot.DOJSCIE_BRAK_POSTEPU_S = 50.0
try:
    def w(d, t, **ustaw):
        d.zeg.t = t
        for kk, vv in ustaw.items():
            setattr(d, kk, vv)
        return d.tick()
    d = atrapa(); LOG.clear()
    r = [w(d, 0.0), w(d, 49.0), w(d, 50.0)]
    sprawdz("11a w IDZ do limitu (50 s) próba trwa", r == ["super"] * 3 and not d.dojscie_porazka, r)
    r = w(d, 51.0)
    sprawdz("11b ponad limit bez nowego idx w IDZ: porażka próby (False) i wpis w logu", r is False and d.dojscie_porazka is True
            and any("bez nowego punktu trasy" in l for l in LOG), (r, LOG[-1:]))
    d = atrapa(); w(d, 0.0)
    r = [w(d, 40.0, idx=2), w(d, 80.0), w(d, 90.0)]
    sprawdz("11c nowy idx zeruje odliczanie (90 s od startu, 50 od idx=2 = jeszcze nie)", r == ["super"] * 3 and not d.dojscie_porazka, r)
    r = w(d, 91.0)
    sprawdz("11d po nowym idx liczy się od nowa: 51 s po idx=2 = porażka", r is False and d.dojscie_porazka, r)
    for stan in ("PAUZA_HP", "WYPAD", "WALKA"):
        d = atrapa(); w(d, 0.0)
        w(d, 60.0, stan=stan)                       # stan inny niż IDZ: odliczanie od 60 s
        r1 = w(d, 100.0, stan="IDZ")                # 40 s od resetu < 50
        r2 = w(d, 109.0)                            # 49 s
        sprawdz(f"11e {stan}: zeruje odliczanie (po 100 s od startu próba trwa)", r1 == "super" and r2 == "super" and not d.dojscie_porazka, (r1, r2))
        r3 = w(d, 111.0)
        sprawdz(f"11f {stan}: po resecie nadal działa limit (51 s w IDZ = porażka)", r3 is False and d.dojscie_porazka, r3)
    cavebot.DOJSCIE_BRAK_POSTEPU_S = 0.0
    d = atrapa(); r = [w(d, 0.0), w(d, 1000.0)]
    sprawdz("11g DOJSCIE_BRAK_POSTEPU_S=0 wyłącza strażnika", r == ["super"] * 2 and not d.dojscie_porazka, r)
    cavebot.DOJSCIE_BRAK_POSTEPU_S = 50.0
    d = atrapa(zegar=False)
    sprawdz("11h atrapa bez zegara: tick nie wywraca się (strażnik się wyłącza)", d.tick() == "super" and not d.dojscie_porazka)
finally:
    cavebot.Cavebot.tick = _tick0; cavebot.log = _log0; cavebot.DOJSCIE_BRAK_POSTEPU_S = _lim0

# 12. znacznik postępu przesuwany o czas czekania na HP (pietra.py: postep[0] += przesuniecie): po 30 s czekania na HP stojąc obok pola
#     i odsunięciu o 2 pola (d = jak przed czekaniem) kandydat NIE jest oddawany za „nie zbliżam się” (limit PIETRA_DOJSCIE_S = 25 s)
s, b = nowy((32663, 31964, 7), hp=80, dojscie=True, idx=3)   # 2 pola od T, HP 80% < próg 90%
pietra.ZASYPANE = {T}
try:
    s.hp_wraca = (200.0, 100)
    b.tick()                                    # _dojdz: postep = [t0, 2]
    st = b.pietra.st
    t0 = st["postep"][0]
    s.poz[:] = list(START)                      # stoimy obok pola: bramka HP czeka
    for _ in range(300):
        b.tick()
        if getattr(b, "hp_czekal_s", 0.0) > 30.0:
            break
    sprawdz("12a czekanie na HP trwa (> 30 s) i przesunęło znacznik postępu", getattr(b, "hp_czekal_s", 0.0) > 30.0 and st["postep"][0] > t0 + 25.0,
            f"czekal={getattr(b, 'hp_czekal_s', 0.0)} postep={st['postep']} t0={t0} t={s.t}")
    s.poz[:] = [32663, 31964, 7]                # odsunięci o 2 pola (walka)
    LOG.clear()
    b.tick()
    sprawdz("12b po odsunięciu: bez „nie zbliżam się” i zmiany kandydata", st["ki"] == 0 and not any("zmieniam kandydata" in l for l in LOG), f"ki={st['ki']} {st['postep']}")
finally:
    pietra.ZASYPANE = {(32493, 32259, 7), (32347, 32123, 7), (32663, 31962, 7)}

print(f"{sum(ok)}/{len(ok)} OK" if all(ok) else f"FAIL {len(ok) - sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
