import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, struct, time
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rdzen

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def wpisz(bufor, idx, ident, nazwa, x, y, z=7, hp=100):
    """Układ jak w _kandydaci_stworow: 4 x 1.0, ID, nazwa, rozmiar, pojemność 15."""
    n = (idx + 5) * 4
    bufor[idx * 4: idx * 4 + 16] = struct.pack("<4f", 1, 1, 1, 1)
    bufor[idx * 4 + 16: idx * 4 + 20] = struct.pack("<I", ident)
    nb = nazwa.encode() + b"\0"
    bufor[n: n + len(nb)] = nb
    bufor[n + 0x10: n + 0x18] = struct.pack("<II", len(nazwa), 15)
    bufor[n + rdzen.POZYCJA_STWORA: n + rdzen.POZYCJA_STWORA + 9] = struct.pack("<IIB", x, y, z)
    bufor[n + rdzen.HP_STWORA] = hp

class Atrapa(rdzen.Pamiec):
    """Pamięć gry z N regionami po 64 KB; zlicza odczyty."""
    def __init__(s, regionow=16):
        super().__init__()
        s.reg = [(0x100000 * (i + 1), 0x100000 * (i + 1) + 0x10000) for i in range(regionow)]
        s.dane = {r: bytearray(0x10000) for r in s.reg}
        s.odczyty = []
        s.mem = object()
    def regiony(s): return list(s.reg)
    def czytaj(s, adres, dl):
        s.odczyty.append(adres)
        for (a, b), d in s.dane.items():
            if a == adres:
                return bytes(d[:dl])
        return b""

GRACZ, SZCZUR = 0x10000001, 0x40000001

# 1. pełny skan znajduje stwory, pole skan/wiek
p = Atrapa()
wpisz(p.dane[p.reg[3]], 100, GRACZ, "Karol", 32000, 32000)
wpisz(p.dane[p.reg[5]], 200, SZCZUR, "Rat", 32001, 32000)
l, info = p.stwory_info(maks_wiek=0)
sprawdz("pelny skan: 2 stwory", [s["nazwa"] for s in l] == ["Karol", "Rat"], l)
sprawdz("skan=pelny", info["skan"] == "pelny" and info["wiek_pelnego_s"] is not None, info)
sprawdz("regiony zebrane (2)", len(p.regiony_stworow) == 2, p.regiony_stworow)

# 2. szybki skan czyta tylko znane regiony
p.odczyty.clear()
p._cache = (p._cache[0], p._cache[1], p._cache[2], time.monotonic())   # pełny świeży
p._skanuj_stwory(False)
sprawdz("szybki skan: 2 regiony", len(p.odczyty) == 2, p.odczyty)
sprawdz("skan=szybki", p._cache[2] == "szybki")

# 3. suma regionów: nowy stwór w innym regionie dokłada, stary nie wypada
wpisz(p.dane[p.reg[9]], 50, 0x40000002, "Cave Rat", 32002, 32001)
p._skanuj_stwory(True)
sprawdz("suma regionów 3", len(p.regiony_stworow) == 3, p.regiony_stworow)
p.dane[p.reg[5]] = bytearray(0x10000)            # szczur zniknął z regionu 5
p._skanuj_stwory(True)
sprawdz("region bez stworów zostaje w sumie", p.reg[5] in p.regiony_stworow)
# limit 12: dokładamy 14 regionów, najstarsze wypadają
p2 = Atrapa(20)
for i in range(14):
    wpisz(p2.dane[p2.reg[i]], 10, 0x40000100 + i, "Rat", 32000 + i, 32000)
    p2._skanuj_stwory(True)
    p2.dane[p2.reg[i]] = bytearray(0x10000)      # stwór odszedł, region zostaje w sumie
    time.sleep(0.002)
sprawdz("limit 12 regionów", len(p2.regiony_stworow) == 12, len(p2.regiony_stworow))
sprawdz("najstarsze wypchnięte", p2.reg[0] not in p2.regiony_stworow and p2.reg[13] in p2.regiony_stworow)

# 4. adaptacja okresu pełnego skanu
p = Atrapa()
wpisz(p.dane[p.reg[3]], 100, GRACZ, "Karol", 32000, 32000)
p._skanuj_stwory(True)
t = time.monotonic()
sprawdz("pusto: pełny po >2 s", not p._potrzebny_pelny(t + 1) and p._potrzebny_pelny(t + 3))
wpisz(p.dane[p.reg[5]], 200, SZCZUR, "Rat", 32001, 32000)
p._skanuj_stwory(True)
t = time.monotonic()
sprawdz("walka: pełny dopiero po >20 s", not p._potrzebny_pelny(t + 10) and p._potrzebny_pelny(t + 21))

# 5. pamięć podręczna i wątek: kolejne zapytania nie skanują ponownie
p.odczyty.clear()
p.stwory_info(); p.stwory_info()
sprawdz("cache: brak odczytów przy świeżym wyniku", len(p.odczyty) == 0, len(p.odczyty))
time.sleep(0.6)
p.odczyty.clear()
l, info = p.stwory_info()
sprawdz("stary cache w walce: szybki skan", info["skan"] == "szybki" and len(p.odczyty) == 2, (info, len(p.odczyty)))

# 6. wątek skanera przez obsluz(); wykrywa nowego stwora bez zapytania synchronicznego
stan = {}
sp = Atrapa()
wpisz(sp.dane[sp.reg[2]], 40, GRACZ, "Karol", 32000, 32000)
rdzen.Pamiec.podlacz = lambda self: 1234          # atrapa: brak procesu gry
rdzen.Pamiec.regiony = lambda self: sp.regiony()
rdzen.Pamiec.czytaj = lambda self, a, d: sp.czytaj(a, d)
real = rdzen.Pamiec(); real.mem = object()
stan["pamiec"] = real
sp = Atrapa()
wpisz(sp.dane[sp.reg[2]], 40, GRACZ, "Karol", 32000, 32000)
sp._cache = None
try:
    r = rdzen.obsluz(stan, {"cmd": "stwory"})
    sprawdz("cmd stwory: pola zgodne + nowe", r["stwory"] and "skan" in r and "wiek_pelnego_s" in r, r.keys())
    wpisz(sp.dane[sp.reg[7]], 60, SZCZUR, "Rat", 32001, 32001)
    t0 = time.monotonic(); znaleziony = None
    while time.monotonic() - t0 < 5:
        c = real._cache
        if c and any(s["nazwa"] == "Rat" for s in c[0]):
            znaleziony = time.monotonic() - t0; break
        time.sleep(0.05)
    sprawdz("wątek tła wykrył nowego stwora <3 s", znaleziony is not None and znaleziony < 3, znaleziony)
finally:
    stan["skaner_token"] = None                     # zatrzymanie wątku

# 7. błąd skanu nie wywraca pętli wątku
class Zepsuta(Atrapa):
    def regiony(s): raise OSError("maps zniknęło")
stan2 = {"pamiec": Zepsuta()}
stan2["pamiec"]._ostatnie_zapytanie = time.monotonic()
tok = object(); stan2["skaner_token"] = tok
import threading
w = threading.Thread(target=rdzen._petla_skanera, args=(stan2, tok), daemon=True); w.start()
time.sleep(0.5)
sprawdz("wątek żyje po błędzie skanu", w.is_alive())
stan2["skaner_token"] = None; w.join(2.5)
sprawdz("wątek kończy się po zmianie tokenu", not w.is_alive())

# 8. komenda "stwor": pozycja/HP + flagi ramek (atakowany, bije_nas) jednym odczytem
class Plaska(Atrapa):
    """czytaj() z dowolnego adresu wewnątrz regionu (komenda stwor czyta od nazwy - 0x24)."""
    def czytaj(s, adres, dl):
        s.odczyty.append(adres)
        for (a, b), d in s.dane.items():
            if a <= adres < b:
                return bytes(d[adres - a: adres - a + dl])
        return b""
pl = Plaska(1)
a0 = pl.reg[0][0]
wpisz(pl.dane[pl.reg[0]], 100, SZCZUR, "Rat", 120, 130, 7, hp=64)
n_nazwy = (100 + 5) * 4
adres = hex(a0 + n_nazwy)
d = pl.dane[pl.reg[0]]
def stwor(**kw): return pl.obsluz({"cmd": "stwor", "adres": adres, "id": SZCZUR, **kw})["stwor"]
r = stwor()
sprawdz("stwor: stare pola (id, x, y, z, hp)", r and (r["id"], r["x"], r["y"], r["z"], r["hp"]) == (SZCZUR, 120, 130, 7, 64), r)
sprawdz("stwor: bez ramek atakowany=False, bije_nas=False", r and r.get("atakowany") is False and r.get("bije_nas") is False, r)
d[n_nazwy + rdzen.RAMKA_STWORA] = 1
d[n_nazwy + rdzen.KOLOR_RAMKI: n_nazwy + rdzen.KOLOR_RAMKI + 16] = struct.pack("<4f", 1, 0, 0, 1)
r = stwor()
sprawdz("stwor: stała czerwona ramka = atakowany", r and r["atakowany"] is True and r["bije_nas"] is False, r)
d[n_nazwy + rdzen.RAMKA_CHWILOWA] = 1
r = stwor()
sprawdz("stwor: ramka chwilowa = bije_nas", r and r["atakowany"] is True and r["bije_nas"] is True, r)
d[n_nazwy + rdzen.RAMKA_STWORA] = 0
r = stwor()
sprawdz("stwor: bije_nas bez atakowany", r and r["atakowany"] is False and r["bije_nas"] is True, r)
sprawdz("stwor: zły id = None", stwor(id=SZCZUR + 5) is None)
# krótki odczyt (stary układ / koniec regionu): stare pola bez flag, bez wyjątku
class Krotka(Plaska):
    def czytaj(s, adres, dl): return super().czytaj(adres, min(dl, -rdzen.POZYCJA_STWORA + rdzen.HP_STWORA + 1))
kr = Krotka(1); kr.dane = pl.dane; kr.reg = pl.reg
r = kr.obsluz({"cmd": "stwor", "adres": adres, "id": SZCZUR})["stwor"]
sprawdz("stwor: krótki odczyt -> pozycja i HP bez flag", r and r["hp"] == 64 and "atakowany" not in r, r)
class Psuje(Plaska):
    @staticmethod
    def _ramka(b, n): raise ValueError("zepsute")
r = Psuje(1); r.dane = pl.dane; r.reg = pl.reg
r = r.obsluz({"cmd": "stwor", "adres": adres, "id": SZCZUR})["stwor"]
sprawdz("stwor: wyjątek w _ramka nie wywraca odpowiedzi", r and r["hp"] == 64 and "atakowany" not in r, r)

# komenda "poscig": pozycja gracza + stwór jednym zapytaniem; "stwor" nadal działa
pl.adres_postaci = a0 + n_nazwy
r = pl.obsluz({"cmd": "poscig", "adres": adres, "id": SZCZUR, "nazwa": "Rat"})
sprawdz("poscig: pozycja gracza i stwór w jednej odpowiedzi",
        r["pozycja"] == {"x": 120, "y": 130, "z": 7} and r["stwor"]["hp"] == 64 and "atakowany" in r["stwor"], r)
r = pl.obsluz({"cmd": "poscig", "adres": adres, "id": SZCZUR + 5, "nazwa": "Rat"})
sprawdz("poscig: zły id stwora = stwor None, pozycja jest", r["stwor"] is None and r["pozycja"]["x"] == 120, r)
sprawdz("stwor: stara komenda bez zmian", stwor() is not None and stwor()["hp"] == 64)
pk = Plaska(1); pk.dane = pl.dane; pk.reg = pl.reg
pk.stwory_info = lambda maks_wiek=None: ([], {"wiek_s": 0.0, "maks": maks_wiek})
sprawdz("stwory: maks_wiek przekazany do cache skanera", pk.obsluz({"cmd": "stwory", "maks_wiek": 0.8})["maks"] == 0.8)

# 9. regresja opóźnienia pościgu: zakresy regionów, które zniknęły z map (sterta urosła), wypadają z sumy
#    przy pełnym skanie (inaczej szybki skan czytał 1,2 GB zamiast ~0,2 GB: 3,2 s zamiast 0,3 s)
class Rosnaca(Atrapa):
    pass
pr = Rosnaca(4)
stary = pr.reg[1]
nowy = (stary[0], stary[1] + 0x10000)                    # ten sam początek, region urósł
pr.dane[nowy] = pr.dane[stary]
wpisz(pr.dane[stary], 100, SZCZUR, "Rat", 32001, 32000)
pr._skanuj_stwory(True)
sprawdz("urosły region: stary zakres w sumie przed zmianą map", stary in pr.regiony_stworow, pr.regiony_stworow)
pr.reg[1] = nowy                                         # mapy po wzroście
pr._skanuj_stwory(True)
sprawdz("po pełnym skanie stary zakres wypada, jest nowy", stary not in pr.regiony_stworow and nowy in pr.regiony_stworow,
        pr.regiony_stworow)
pr.odczyty.clear(); pr._skanuj_stwory(False)
sprawdz("szybki skan czyta tylko bieżące regiony (1)", len(pr.odczyty) == 1, pr.odczyty)

# 10. czas szybkiego skanu: budżet (offline, 12 regionów po 4 MB) < 0,5 s; wiek danych w cache <= 0,5 s
class Duza(Atrapa):
    def __init__(s):
        rdzen.Pamiec.__init__(s)
        s.reg = [(0x1000000 * (i + 1), 0x1000000 * (i + 1) + (4 << 20)) for i in range(12)]
        s.dane = {r: bytearray(4 << 20) for r in s.reg}
        s.odczyty = []; s.mem = object()
du = Duza()
wpisz(du.dane[du.reg[3]], 100, SZCZUR, "Rat", 32001, 32000)
du._skanuj_stwory(True)
t = time.monotonic(); du._skanuj_stwory(False); dt = time.monotonic() - t
sprawdz(f"szybki skan 12 regionów offline < 0,5 s ({dt:.3f} s)", dt < 0.5, dt)

# 11. zapytanie przy trwającym skanie czeka krótko (CZEKANIE_NA_SKAN) i dostaje świeży cache, nie stary
import threading
bz = Atrapa(2)
wpisz(bz.dane[bz.reg[0]], 100, SZCZUR, "Rat", 32001, 32000)
bz._skanuj_stwory(True)
bz._zamek = threading.Lock()
bz._cache = (bz._cache[0], time.monotonic() - 1.0, "szybki", time.monotonic())   # cache 1 s
bz._zamek.acquire()
def zwolnij():
    time.sleep(0.2); bz._cache = (bz._cache[0], time.monotonic(), "szybki", bz._cache[3]); bz._zamek.release()
threading.Thread(target=zwolnij, daemon=True).start()
t = time.monotonic(); l, info = bz.stwory_info(maks_wiek=0.4); dt = time.monotonic() - t
sprawdz(f"skan w toku: odpowiedź po ~0,2 s ze świeżym cache (wiek {info['wiek_s']}, czekanie {dt:.2f} s)",
        info["wiek_s"] < 0.15 and dt < 0.5, (info, dt))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
