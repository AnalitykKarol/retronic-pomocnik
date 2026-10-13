"""Testy 12.10: patrol po miejscach (cavebot._idz_patrol), zakaz zmiany piętra w pościgu, poprawki lootu.
Offline, na prawdziwej mapie serwera i trasy/miejsca.json."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, json, random, tempfile, pathlib
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot, bot, mapa as _mapa
import pokretla as _pk

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.log = lambda *a: None
MAPA = _mapa.mapa()
KANALY = [tuple(p) for p in json.loads((cavebot.KATALOG_TRAS / "kanaly2.json").read_text())]
MIEJSCA = json.loads((cavebot.KATALOG_TRAS / "miejsca.json").read_text())["miejsca"]


class Swiat:
    def __init__(s, poz, hp=100):
        s.t = 0.0; s.poz = list(poz); s.hp = hp; s.stwory = []; s.ataki = []; s.zajal = []
        s.schody = {}   # (x,y,z) -> (x,y,z) po wejściu
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k):
        s = p.s
        if k not in bot.KIERUNKI: return
        d = bot.KIERUNKI[k]; s.t += 0.2
        n = (s.poz[0] + d[0], s.poz[1] + d[1], s.poz[2])
        if MAPA.przechodnie(*n) is not True and n not in s.schody: return
        if any((m["x"], m["y"]) == n[:2] and m.get("hp", 100) > 0 for m in s.stwory): return
        if n in s.schody:
            s.poz[:] = list(s.schody[n]); s.zmiany = getattr(s, "zmiany", 0) + 1
        else:
            s.poz[:] = list(n)
        s.zajal.append(tuple(s.poz))
    def krok(p, k): p.klawisz(k); return tuple(p.s.poz)

def swiat_bot(poz, **kw):
    s = Swiat(poz)
    def atak(m, g):
        s.ataki.append((m["id"], s.t))
        for x in s.stwory:
            if x["id"] == m["id"]: x["hp"] -= 50
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    b = cavebot.Cavebot(P(s), KANALY, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=MAPA, czas_s=10 ** 7, **kw)
    return s, b

def bieg(b, n, stop=None):
    for i in range(n):
        if not b.tick(): return i
        if stop and stop(): return i
    return n

# ---------- 1. wczytanie miejsc, tryb ----------
cavebot.TRYB_PATROL = 1
cavebot.PATROL_POSTOJ = (0.2, 0.4)
s, b = swiat_bot((32016, 32146, 11))
sprawdz("1a wczytano 22 miejsca", len(b._patrol_wczytaj()) == 22, len(b.miejsca or []))
sprawdz("1b patrol aktywny przy TRYB_PATROL=1 i mapie", b._patrol_aktywny())
cavebot.TRYB_PATROL = 0
sprawdz("1c TRYB_PATROL=0 -> pętla trasy", not b._patrol_aktywny())
cavebot.TRYB_PATROL = 1

# ---------- 2. ważenie ----------
random.seed(12)
m = {x["id"]: x for x in b.miejsca}
w14 = b._patrol_waga(m[14], 15, []); w1 = b._patrol_waga(m[17], 15, [])
sprawdz("2a miejsce bez danych ma wagę min (>0), a gęste zabicia wyższą", 0 < w1 < w14 and abs(w1 - cavebot.PATROL_WAGA_MIN / (1 + 15 / cavebot.PATROL_ODL_SKALA)) < 1e-9, (w1, w14))
sprawdz("2b bliżej = lepiej przy tym samym udziale", b._patrol_waga(m[14], 5, []) > b._patrol_waga(m[14], 40, []))
sprawdz("2c ostatnie 4 wykluczone, 5-8 z karą", b._patrol_waga(m[14], 15, [14, 1, 2, 3]) == 0.0
        and b._patrol_waga(m[14], 15, [14, 1, 2, 3, 4, 5, 6, 7]) < w14 * 0.5 + 1e-12
        and b._patrol_waga(m[14], 15, [14, 1, 2, 3, 4, 5, 6, 7]) > 0)
licz = {}
poz0 = (32030, 32150, 11)
for _ in range(1500):
    b.patrol_pierwszy = False; b.patrol_blok.clear()
    p = b._patrol_wybierz(poz0)
    licz[p["m"]["id"]] = licz.get(p["m"]["id"], 0) + 1
zach = sum(licz.get(i, 0) for i in (1, 2, 3, 4, 5, 6, 7, 10))
sprawdz("2d id14 wybierane najczęściej, ale nie wyłącznie", licz.get(14, 0) == max(licz.values()) and licz[14] < 1500 * 0.6, licz)
sprawdz("2e zachodnie (bez danych) też bywają odwiedzane", zach > 0 and len([i for i in licz if i in (1, 2, 3, 4, 5, 6, 7, 10)]) >= 3, zach)

# ---------- 2'. pole "waga", zachód, pokrętło PATROL_WAGA_MIN ----------
W_ZACH = (1, 2, 3, 4, 5, 6, 7, 8, 10)
sprawdz("2f miejsca.json: pole waga ustawione dla id 1-8,10 (0.05-0.2), poza tym brak",
        all(0.05 <= x["waga"] <= 0.2 for x in MIEJSCA if x["id"] in W_ZACH)
        and not any("waga" in x for x in MIEJSCA if x["id"] not in W_ZACH))
mw = {x["id"]: x for x in b._patrol_wczytaj()}
sprawdz("2g _patrol_wczytaj przenosi waga", mw[1]["waga"] == 0.12 and mw[14]["waga"] is None, (mw[1]["waga"], mw[14]["waga"]))
sprawdz("2h waga zastępuje max(udział, MIN): id1 = 0.12/(1+d/skala)",
        abs(b._patrol_waga(mw[1], 15, []) - 0.12 / (1 + 15 / cavebot.PATROL_ODL_SKALA)) < 1e-9)
def _udzial_zachodu(poz, n=2000):
    c = 0
    for _ in range(n):
        b.patrol_pierwszy = False; b.patrol_blok.clear(); b.patrol_historia.clear()
        if b._patrol_wybierz(poz)["m"]["id"] in W_ZACH: c += 1
    return c / n
random.seed(3)
u14 = _udzial_zachodu((mw[14]["x"], mw[14]["y"], 11)); u21 = _udzial_zachodu((mw[21]["x"], mw[21]["y"], 11))
sprawdz("2i zachód dostaje ok. 40-60% losowań z id14 i 30-50% z id21 (2000 losowań)", 0.40 <= u14 <= 0.62 and 0.30 <= u21 <= 0.50, (u14, u21))
# wykluczenie ostatnich 4 nadal działa dla miejsca z wagą
sprawdz("2j ostatnie 4 wykluczone także przy polu waga", b._patrol_waga(mw[1], 15, [1, 2, 3, 4]) == 0.0)
# pokrętło PATROL_WAGA_MIN: zakres 0-0.5, działa na miejsca bez pola waga, hot-reload
sprawdz("2k pokrętło PATROL_WAGA_MIN w ZAKRESY (0, 0.5)", _pk.ZAKRESY.get("PATROL_WAGA_MIN") == (0.0, 0.5))
_ok, _bl = _pk.waliduj({"PATROL_WAGA_MIN": 0.2})
_ok2, _bl2 = _pk.waliduj({"PATROL_WAGA_MIN": 0.6})
sprawdz("2l walidacja: 0.2 ok, 0.6 odrzucone", _ok == {"PATROL_WAGA_MIN": 0.2} and _bl2 and not _ok2)
_tmp = pathlib.Path(tempfile.mkdtemp()) / "na_zywo.json"
_pr = _pk.Pokretla(cavebot, plik=_tmp, log=lambda *a: None)
_dom = cavebot.PATROL_WAGA_MIN
_tmp.write_text(json.dumps({"PATROL_WAGA_MIN": 0.3})); _pr.odswiez()
sprawdz("2m hot-reload ustawia PATROL_WAGA_MIN i podbija wagę miejsca bez pola waga",
        cavebot.PATROL_WAGA_MIN == 0.3 and abs(b._patrol_waga(mw[15], 15, []) - 0.3 / (1 + 15 / cavebot.PATROL_ODL_SKALA)) < 1e-9
        and abs(b._patrol_waga(mw[1], 15, []) - 0.12 / (1 + 15 / cavebot.PATROL_ODL_SKALA)) < 1e-9)
_tmp.write_text("{}"); _pr.mtime = None; _pr.odswiez()
sprawdz("2n usunięcie klucza = powrót do domyślnej", cavebot.PATROL_WAGA_MIN == _dom, cavebot.PATROL_WAGA_MIN)

# ---------- 2b. po walce: powrót do pierwotnego celu (PATROL_POWROT_DO_CELU) ----------
def _po_walce(start, cel_id, blok=False, powrot=1):
    stare = cavebot.PATROL_POWROT_DO_CELU; cavebot.PATROL_POWROT_DO_CELU = powrot
    cavebot.PATROL_SWEEP = 0
    try:
        s, bb = swiat_bot(start)
        mm = next(x for x in bb._patrol_wczytaj() if x["id"] == cel_id)
        bb.patrol = bb._patrol_nowy(start, mm, "test")
        bb.patrol["tick"] = s.t - 30.0          # przerwa (walka) > PATROL_LUKA_S
        if blok: bb.patrol_blok[cel_id] = s.t + 100
        bb.patrol_historia.clear()
        bb._idz_patrol()
        return bb.patrol["m"]["id"] if bb.patrol else None
    finally:
        cavebot.PATROL_POWROT_DO_CELU = stare; cavebot.PATROL_SWEEP = 1
sprawdz("2o po walce na m7, cel m1 (21 pól): zostaje przy m1", _po_walce((32002, 32136, 11), 1) == 1)
sprawdz("2p pokrętło 0: po walce bierze miejsce tuż obok (m7)", _po_walce((32002, 32136, 11), 1, powrot=0) == 7)
sprawdz("2q pierwotny cel zablokowany: bierze miejsce obok (m7)", _po_walce((32002, 32136, 11), 1, blok=True) == 7)
sprawdz("2r cel dalej niż 40 pól: dawne zachowanie (m21 obok)", _po_walce((32044, 32158, 11), 1) == 21)
sprawdz("2s miejsce <= 2 pola leżące w kierunku celu: zmiana na nie", _po_walce((32004, 32136, 11), 1) == 7)

# ---------- 3. brak powtórzeń ----------
b.patrol_historia.clear(); b.patrol_blok.clear(); b.patrol_pierwszy = False
pozb = poz0; ciag = []; powt = 0
for _ in range(300):
    p = b._patrol_wybierz(pozb)
    mid = p["m"]["id"]
    if mid in ciag[-4:]: powt += 1
    ciag.append(mid); b.patrol_historia.append(mid)
    pozb = (p["m"]["x"], p["m"]["y"], 11)
sprawdz("3 żadne miejsce nie powtarza się w ostatnich 4 wizytach (300 wyborów)", powt == 0 and len(set(ciag)) >= 15, (powt, len(set(ciag))))

# ---------- 4. droga A*: różne ścieżki i dojście do wszystkich 22 miejsc ----------
s, b = swiat_bot((32016, 32146, 11))
nieosiag = []
dl = {}
b._patrol_wczytaj()
for x in b.miejsca:
    d = b.droga((32016, 32146, 11), (x["x"], x["y"]), dlugosc=0)
    if d is None: nieosiag.append(x["id"])
    else: dl[x["id"]] = len(d)
sprawdz("4a A* z id14 do wszystkich 22 miejsc istnieje", not nieosiag and len(dl) == 22, (nieosiag, dl))

cavebot.PATROL_SWEEP = 0      # 4b/4c: sam marsz A* do każdego miejsca (sweep osobno w sekcji 13)
def dojdz(start, mid, limit=900):
    s, b = swiat_bot(start)
    mm = next(x for x in b._patrol_wczytaj() if x["id"] == mid)
    b.patrol = b._patrol_nowy(start, mm, "test")
    if b.patrol is None: return None
    n = bieg(b, limit, lambda: b.patrol["faza"] != "dojscie" if b.patrol else True)
    return (b.patrol is not None and b.patrol["faza"] != "dojscie", n, tuple(s.poz), s)
wyn = {}
for x in MIEJSCA:
    r = dojdz((32016, 32146, 11), x["id"])
    wyn[x["id"]] = r and r[0]
sprawdz("4b symulacja marszu: patrol z id14 dochodzi do wszystkich 22 miejsc", all(wyn.values()) and len(wyn) == 22,
        [i for i, v in wyn.items() if not v])
wyn2 = {}
for x in MIEJSCA:
    st = (32044, 32158, 11)
    r = dojdz(st, x["id"]) if x["id"] != 21 else (True,)
    wyn2[x["id"]] = r and r[0]
sprawdz("4c to samo z id21 (wschód)", all(wyn2.values()), [i for i, v in wyn2.items() if not v])

cavebot.PATROL_SWEEP = 1
# ---------- 5. pełny patrol: odwiedziny, postój, KPI ----------
random.seed(5)
s, b = swiat_bot((32016, 32146, 11))
logi = []
cavebot.log = lambda *a: logi.append(" ".join(map(str, a)))
bieg(b, 30000, lambda: b.patrol_wizyty >= 25)
cavebot.log = lambda *a: None
b._patrol_wczytaj()
sprawdz("5a bot odwiedził >= 25 miejsc w patrolu", b.patrol_wizyty >= 25, b.patrol_wizyty)
sprawdz("5b KPI per miejsce zapisane", sum(v["wizyty"] for v in b.patrol_stat.values()) == b.patrol_wizyty and any("Patrol: wizyta" in l for l in logi))
sprawdz("5c pierwszy wybór = najbliższe miejsce (id14, stoimy na nim)", any("najbliższe" in l and "m14" in l for l in logi), logi[:3])
ostatnie = b.patrol_historia
powt = sum(1 for i in range(len(ostatnie)) if ostatnie[i] in ostatnie[max(0, i - 4):i])
sprawdz("5d w historii wizyt brak powtórzeń w oknie 4", powt == 0, ostatnie)
sprawdz("5e piętro się nie zmieniło", s.poz[2] == 11 and not getattr(s, "zmiany", 0))

# ---------- 6. kill KPI ----------
s, b = swiat_bot((32016, 32146, 11))
b.patrol_zabicia = 0
b.cel = {"id": 7, "nazwa": "Rat", "poz": (32017, 32146, 11), "odl": 1}
b.zgon_celu({"hp": 100, "max_hp": 100, "proc": 100}, (32016, 32146, 11), pewny=True)
sprawdz("6 zgon celu liczy się do KPI patrolu", b.patrol_zabicia == 1)

# ---------- 7. fallback ----------
tmp = pathlib.Path(tempfile.mkdtemp())
stare = cavebot.KATALOG_TRAS
cavebot.KATALOG_TRAS = tmp
try:
    s, b = swiat_bot((32016, 32146, 11))
    sprawdz("7a brak miejsca.json -> patrol nieaktywny (fallback na trasę)", not b._patrol_aktywny() and b.miejsca == [])
    n = bieg(b, 30)
    sprawdz("7b bot chodzi po trasie zamiast patrolu", n == 30 and b.patrol is None)
    (tmp / "miejsca.json").write_text("{zepsute")
    s, b = swiat_bot((32016, 32146, 11))
    sprawdz("7c uszkodzony plik -> fallback", not b._patrol_aktywny())
finally:
    cavebot.KATALOG_TRAS = stare
# brak drogi do żadnego miejsca (inne piętro): fallback i jazda trasą
s, b = swiat_bot((32016, 32146, 11))
b._patrol_wczytaj()
for x in b.miejsca: x["z"] = 5
r = b._idz_patrol()
sprawdz("7d żadne miejsce na piętrze -> None + okno fallbacku", r is None and b.patrol_fallback_do > s.t)
sprawdz("7e idz() w oknie fallbacku jedzie trasą", b.idz() in (True, False) and b.patrol is None)
# mapa niedostępna
s, b = swiat_bot((32016, 32146, 11)); b.mapa = None
sprawdz("7f bez mapy patrol nieaktywny", not b._patrol_aktywny())

# ---------- 8. gracze: miejsca przy graczu pomijane ----------
s, b = swiat_bot((32016, 32146, 11)); b._patrol_wczytaj()
b.unikanie.aktywne = True; b.unikanie.gracze = [{"x": 32015, "y": 32137, "z": 11, "nazwa": "X", "odl": 9, "id": 9}]
kand = {x["id"] for x, _ in b._patrol_kandydaci((32016, 32146, 11))}
sprawdz("8 miejsce id13 przy graczu pominięte", 13 not in kand and 14 in kand, sorted(kand))

# ---------- 9. wypad -> najbliższe miejsce; model zmienia trasę -> patrol off ----------
s, b = swiat_bot((32030, 32150, 11)); b._patrol_wczytaj()
b.patrol = b._patrol_wybierz((32030, 32150, 11))
b._wypad_wroc_na_trase((32030, 32150, 11))
sprawdz("9a po wypadzie patrol zresetowany, następny wybór najbliższy", b.patrol is None and b.patrol_pierwszy)
b.patrol_wylacz("test")
sprawdz("9b patrol_wylacz", not b._patrol_aktywny())

# ---------- 10. zakaz zmiany piętra ----------
s, b = swiat_bot((32049, 32155, 11))
sprawdz("10a pole schodów (32050,32155,11) zakazane", b.pole_zmiany_pietra((32050, 32155, 11)))
sprawdz("10b zwykłe pole nie", not b.pole_zmiany_pietra((32046, 32155, 11)))
b.wypad_aktywny = True
sprawdz("10c w wypadzie zakaz wyłączony", not b.pole_zmiany_pietra((32050, 32155, 11)))
b.wypad_aktywny = False
cavebot.POSCIG_BEZ_ZMIANY_PIETRA = False
sprawdz("10d pokrętło 0 wyłącza zakaz", not b.pole_zmiany_pietra((32050, 32155, 11)))
cavebot.POSCIG_BEZ_ZMIANY_PIETRA = True
d = b.droga((32049, 32155, 11), (32051, 32156), dlugosc=0)
sprawdz("10e droga omija schody", d is None or all(tuple(q[:2]) != (32050, 32155) for q in d), d)
r = b.krok_prosto((32052, 32155), (32049, 32155, 11), pauza=False) if False else None
sprawdz("10f krok_prosto nie wchodzi na schody", b.krok_prosto((32052, 32155), (32049, 32155, 11), pauza=False) is None
        and tuple(s.poz) == (32049, 32155, 11))
lista = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 32050, "y": 32155, "z": 11, "hp": 30},
         {"id": 6, "nazwa": "Rat", "gracz": False, "x": 32048, "y": 32155, "z": 11, "hp": 30}]
k = b.kandydaci(lista, (32046, 32155, 11))
sprawdz("10g mob na schodach dalej niż 1 pole nie jest celem, zwykły tak", [x["id"] for x in k] == [6], k)
k = b.kandydaci(lista, (32049, 32155, 11))
sprawdz("10h mob na schodach obok (odl 1) nadal bity", 5 in [x["id"] for x in k])
# symulacja: szczur za schodami, bot nigdy nie wchodzi na schody
s, b = swiat_bot((32049, 32155, 11))
s.schody = {(32050, 32155, 11): (32050, 32156, 10)}
s.stwory = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 32052, "y": 32155, "z": 11, "hp": 40}]
bieg(b, 80)
sprawdz("10i pościg: bot zostaje na z11 (nie wchodzi po schodach)", s.poz[2] == 11 and not getattr(s, "zmiany", 0), (s.poz, getattr(s, "zmiany", 0)))
# kontrola: bez zakazu bot wszedłby na schody (test wiarygodny)
cavebot.POSCIG_BEZ_ZMIANY_PIETRA = False
s, b = swiat_bot((32049, 32155, 11))
s.schody = {(32050, 32155, 11): (32050, 32156, 10)}
s.stwory = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 32052, "y": 32155, "z": 11, "hp": 40}]
bieg(b, 80)
kontrola = s.poz[2] != 11 or getattr(s, "zmiany", 0)
cavebot.POSCIG_BEZ_ZMIANY_PIETRA = True
print("INFO kontrola bez zakazu: zmiana piętra =", bool(kontrola))

# ---------- 11. loot ----------
sprawdz("11a LOOT_RETRY_DALEJ=0, LOOT_MAKS_PROB=4", cavebot.LOOT_RETRY_DALEJ == 0 and cavebot.LOOT_MAKS_PROB == 4)
def _loot(wyniki, niedok, zywe=False):
    s, b = swiat_bot((100, 100, 7)); b.mapa = None
    s.poz[:] = [100, 100, 7]
    if zywe:
        s.stwory = [{"id": 9, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 50}]
    wyw = []
    def zb(zw, g):
        wyw.append(1)
        ns.NIEDOKONCZONE = niedok and len(wyw) < len(wyniki)
        return wyniki[min(len(wyw), len(wyniki)) - 1]
    ns = types.SimpleNamespace(zbierz=zb, PROBOWANE={}, NIEDOKONCZONE=False)
    b.loot = ns
    return b, wyw
b, wyw = _loot(["brak_okna", "ok"], True)
w = b.zbierz_loot((101, 100, 7))
sprawdz("11b brak_okna + zostały pola + brak mobów -> jedno lokalne ponowienie", len(wyw) == 2 and w == "ok", (len(wyw), w))
b, wyw = _loot(["brak_okna", "brak_okna", "ok"], True)
w = b.zbierz_loot((101, 100, 7))
sprawdz("11c tylko jedno ponowienie lokalne", len(wyw) == 2 and w == "brak_okna", (len(wyw), w))
b, wyw = _loot(["brak_okna", "ok"], True, zywe=True)
w = b.zbierz_loot((101, 100, 7))
sprawdz("11d żywy mob w widoku -> bez lokalnego ponowienia (decyduje model)", len(wyw) == 1 and w == "brak_okna", (len(wyw), w))
b, wyw = _loot(["brak_okna", "ok"], False)
w = b.zbierz_loot((101, 100, 7))
sprawdz("11e wszystkie pola sprawdzone (NIEDOKONCZONE False) -> bez ponowienia", len(wyw) == 1, len(wyw))
cavebot.LOOT_PONOW_LOKALNIE = 0
b, wyw = _loot(["brak_okna", "ok"], True)
w = b.zbierz_loot((101, 100, 7))
cavebot.LOOT_PONOW_LOKALNIE = 1
sprawdz("11f LOOT_PONOW_LOKALNIE=0 wyłącza", len(wyw) == 1, len(wyw))

# ---------- 12. pokrętła ----------
import pokretla as _pk
sprawdz("12 pokrętła: TRYB_PATROL, POSCIG_BEZ_ZMIANY_PIETRA, LOOT_PONOW_LOKALNIE w ZAKRESY",
        all(k in _pk.ZAKRESY for k in ("TRYB_PATROL", "POSCIG_BEZ_ZMIANY_PIETRA", "LOOT_PONOW_LOKALNIE"))
        and "POSCIG_BEZ_ZMIANY_PIETRA" in _pk.KIERUNEK)

# ---------- 13. sweep zachodu, czas od ostatniej wizyty, powrót po walce ----------
TRASA_Z = [tuple(q) for q in json.loads((cavebot.KATALOG_TRAS / "nowe_miejsca.json").read_text())]
POLA_Z = set(q[:2] for q in TRASA_Z)
def _sweep_start(start=(32016, 32146, 11), mid=3):
    s, bb = swiat_bot(start)
    mm = next(x for x in bb._patrol_wczytaj() if x["id"] == mid)
    bb.patrol = bb._patrol_nowy(start, mm, "test")
    return s, bb
s, b = _sweep_start()
sprawdz("13a cel B (m3) dostaje sweep po nagranej trasie", b.patrol and b.patrol.get("sweep") and len(b.patrol["seg"]) >= len(POLA_Z) * 0.8,
        (len(b.patrol["seg"]) if b.patrol else None, len(POLA_Z)))
cavebot.log = lambda *a: None
bieg(b, 6000, lambda: b.patrol["faza"] != "dojscie")
odw = set(tuple(q[:2]) for q in s.zajal)
pokr = sum(1 for q in POLA_Z if q in odw) / len(POLA_Z)
sprawdz("13b sweep przeszedł >= 90% pól trasy zachodu", pokr >= 0.9, round(pokr, 3))
zal = {i for i in b.patrol_historia}
bpl = {x["id"] for x in MIEJSCA if x.get("zrodlo") == "B"}
sprawdz("13c po sweepie miejsca B przy trasie zaliczone (>= 8 z 10 B)", len(zal & bpl) >= 8 and 3 in zal, sorted(zal))
sprawdz("13d przerwa między sweepami: kolejny cel B bez sweepu", (lambda: (
    setattr(b, "patrol", None), b._patrol_nowy((32002, 32136, 11), next(x for x in b.miejsca if x["id"] == 5), "t"))[1])().get("sweep") is None)
b.sweep_wschod = 5; s.t += cavebot.PATROL_SWEEP_MIN_S + 1
p2 = b._patrol_nowy((32016, 32146, 11), next(x for x in b.miejsca if x["id"] == 5), "t")
sprawdz("13e po przerwie i wizytach na wschodzie sweep znów możliwy", p2 and p2.get("sweep"))
cavebot.PATROL_SWEEP = 0
p3 = _sweep_start()[1].patrol
sprawdz("13f PATROL_SWEEP=0: zwykła droga, bez sweepu", p3 and not p3.get("sweep"))
cavebot.PATROL_SWEEP = 1
# czas od ostatniej wizyty
s, b = swiat_bot((32016, 32146, 11)); mw2 = {x["id"]: x for x in b._patrol_wczytaj()}
w0 = b._patrol_waga(mw2[15], 15, []); s.t += 600.0
w1 = b._patrol_waga(mw2[15], 15, []); b.patrol_ost[15] = s.t - 30
w2 = b._patrol_waga(mw2[15], 15, []); s.t += 100000
w3 = b._patrol_waga(mw2[15], 15, [])
sprawdz("13g waga rośnie z czasem od wizyty (x3 po 600 s, x1.1 po 30 s, max x4)",
        abs(w1 / w0 - 3.0) < 1e-6 and abs(w2 / w0 - 1.1) < 1e-6 and abs(w3 / w0 - 4.0) < 1e-6, (w0, w1, w2, w3))
cavebot.PATROL_CZAS_MAX = 0
sprawdz("13h PATROL_CZAS_MAX=0 wyłącza", abs(b._patrol_waga(mw2[15], 15, []) - w0) < 1e-9)
cavebot.PATROL_CZAS_MAX = 3.0
# powrót po walce: sweep trwa, mimo że obok jest inne miejsce
s, b = _sweep_start()
bieg(b, 120)
p = b.patrol
b.patrol_historia.clear()
p["tick"] = s.t - 30.0
b._idz_patrol()
sprawdz("13i po walce wracamy do przerwanego sweepu (ten sam patrol)", b.patrol is p and p.get("sweep") is not None and p["m"]["id"] == 3,
        (b.patrol["m"]["id"], tuple(s.poz)))
# zejście z drogi (walka/ucieczka): replan nadal prowadzi przez resztę trasy
nast0 = p["sweep"]["nast"]
s.poz[:] = [32010, 32147, 11] if MAPA.przechodnie(32010, 32147, 11) is True else s.poz
p["replan"] = -10.0; p["seg_xy"] = set()
b._idz_patrol()
sprawdz("13j replan sweepu: odcinek obejmuje resztę trasy (nie prosto do końca)", len(p["seg"]) >= (len(p["sweep"]["trasa"]) - p["sweep"]["nast"]) * 0.8,
        (len(p["seg"]), p["sweep"]["nast"]))
# rozkład zachód / wschód w długiej symulacji
random.seed(8)
s, b = swiat_bot((32016, 32146, 11)); b._patrol_wczytaj()
bieg(b, 60000, lambda: b.patrol_wizyty >= 60)
zachB = {i for i in bpl}
vis = {i: v["wizyty"] for i, v in b.patrol_stat.items()}
w = sum(v for i, v in vis.items() if i in zachB); e = sum(v for i, v in vis.items() if i not in zachB)
print("INFO rozkład wizyt (sweep): zachód B", w, "wschód", e, "czas sym.", round(s.t), vis)
sprawdz("13k zachód i wschód odwiedzane (zachód 30-70% wizyt)", w + e >= 40 and 0.3 <= w / (w + e) <= 0.7, (w, e))

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
