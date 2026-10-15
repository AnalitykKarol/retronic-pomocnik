import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot
cavelog = []
_log0 = cavebot.log
def _log(*a): cavelog.append(" ".join(map(str, a))); _log0(*a)
cavebot.log = _log
# testy scenariuszy są deterministyczne; losowe dodatki sprawdzają osobne testy na końcu
LOSOWE = dict(REAKCJA=cavebot.REAKCJA, DRUGI_CEL=cavebot.DRUGI_CEL, ROZRZUT_PROGU=cavebot.ROZRZUT_PROGU,
              ODWROCENIE_TRASY=cavebot.ODWROCENIE_TRASY, SCINANIE=cavebot.SCINANIE,
              PAUZA_KROTKA=cavebot.PAUZA_KROTKA, PAUZA_DLUGA=cavebot.PAUZA_DLUGA)
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0     # 13.10 P2a: strażnik celu ma własny test (test_straznik_celu.py); tu długie walki ze stałym HP
cavebot.CZEKAJ_BLISKO = 0   # testy odpuszczania objazdu: stare zachowanie (bliskie cele - sekcja 18c)
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False   # sekcje 1-34 testują dawne zachowanie (klik z dystansu); sekcja 35 włącza nowe

class Swiat:
    def __init__(s, poz=(100,100,7), hp=100, max_hp=100):
        s.t = 0.0; s.poz = list(poz); s.hp = hp; s.max_hp = max_hp
        s.stwory = []; s.klawisze = []; s.ataki = []; s.alarmy = []; s.regen = False
        s.zabija = True   # atak zbija HP celu
        s.ucieka = False
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": s.max_hp, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        if p.s.ucieka:
            for m in p.s.stwory: m["x"] += 1 if m["x"] >= p.s.poz[0] else 0
        return tuple(p.s.poz)
def zrob(s, punkty, **kw):
    def atak(m, g):
        assert abs(m["x"]-g["x"]) <= 7 and abs(m["y"]-g["y"]) <= 5, "atak poza widokiem"
        s.ataki.append((m["id"], s.t))
        for x in s.stwory:
            if x["id"] == m["id"] and s.zabija: x["hp"] -= 50
    lootlog = []
    def zbierz(zwloki, gracz):
        lootlog.append(zwloki)
        s.loot_gracz = tuple(gracz)
        assert max(abs(zwloki[0]-gracz[0]), abs(zwloki[1]-gracz[1])) <= 1, "loot z daleka"
        return "ok"
    loot = types.SimpleNamespace(zbierz=zbierz)
    b = cavebot.Cavebot(P(s), punkty, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: s.alarmy.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot, **kw)
    b.lootlog = lootlog
    return b
def bieg(b, s, ticki, fn=None):
    for i in range(ticki):
        if fn: fn(i)
        if not b.tick(): return i
    return ticki
def trasa(): return [(100+i,100,7) for i in range(1,11)]
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

# 1. potwor obok: bij do smierci, loot
s = Swiat(); s.stwory = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1)
def usun(i):
    s.stwory[:] = [m for m in s.stwory if m["hp"] > 0 or m.__setitem__("hp", 0) or True and False] if False else s.stwory
for i in range(30):
    b.tick()
    s.stwory[:] = [m for m in s.stwory if m["hp"] > 0]   # zwloki znikaja z listy
sprawdz("1 potwor obok -> atak + zgon + loot", len(s.ataki) >= 1 and b.lootlog == [(101,100,7)], f"ataki={len(s.ataki)} loot={b.lootlog}")

# 1b. potwor daleko, tryb --czekaj: najpierw czeka, potem podchodzi
s = Swiat(); s.stwory = [{"id": 6, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1); s.zabija = False; b.czekaj = True
bieg(b, s, 2)
sprawdz("1b' potwor 5 pol dalej -> najpierw atak i czekanie w miejscu", s.poz[0] == 100 and len(s.ataki) >= 1, f"poz={s.poz} ataki={len(s.ataki)}")
bieg(b, s, 60)
sprawdz("1b potwor stoi -> po czekaniu podchodzi", s.poz[0] >= 103, f"poz={s.poz}")

# 1f. potwor sam podchodzi, tryb --czekaj: bot stoi w miejscu
s = Swiat(); s.stwory = [{"id": 7, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1); s.zabija = False; b.czekaj = True
zrzuty = []; t_obok = [None]
def ramka(stwor, gracz):
    zrzuty.append((s.t, max(abs(stwor["x"] - gracz["x"]), abs(stwor["y"] - gracz["y"])))); return False
b.czy_atakowany = ramka
def podchodzi(i):
    if i % 3 == 2 and s.stwory[0]["x"] > 101:
        s.stwory[0]["x"] -= 1
        if s.stwory[0]["x"] == 101: t_obok[0] = s.t
bieg(b, s, 14, podchodzi)
sprawdz("1f potwor podchodzi -> bot czeka w miejscu", s.poz[0] == 100 and s.stwory[0]["x"] == 101, f"poz={s.poz} potwor x={s.stwory[0]['x']}")
przed = [a for a in s.ataki if a[1] < t_obok[0]]
sprawdz("1f' daleki cel: tylko pierwszy atak, bez ponowień i zrzutów ramki, zanim podejdzie",
        len(przed) == 1 and all(o <= 1 for _, o in zrzuty), f"ataki przed={[round(a[1],1) for a in przed]} zrzuty={zrzuty[:3]}")

# 1c. ponawianie ataku gdy HP nie spada (dopiero gdy potwór stoi obok; pierwszy atak był z daleka)
for _ in range(40): b.tick()
obok_ataki = [a for a in s.ataki if a[1] >= t_obok[0]]
sprawdz("1c ponowienie ataku co 2-3.5 s bez spadku HP, od razu po podejściu",
        len(obok_ataki) >= 3 and obok_ataki[0][1] - t_obok[0] <= 1.5
        and all(2.0 <= y[1]-x[1] <= 4.1 for x,y in zip(obok_ataki, obok_ataki[1:])),
        f"obok od t={t_obok[0]:.1f}, ataki t={[round(a[1],1) for a in s.ataki]}")

# 1d. potwor z innego pietra / poza ekranem ignorowany; filtr nazw
s = Swiat(); s.stwory = [{"id": 7, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 8, "hp": 100},
                         {"id": 8, "nazwa": "Rat", "gracz": False, "x": 130, "y": 100, "z": 7, "hp": 100},
                         {"id": 9, "nazwa": "Troll", "gracz": False, "x": 101, "y": 101, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1, potwory=["rat"])
bieg(b, s, 5)
sprawdz("1d inne pietro/daleko/zly gatunek ignorowane", not s.ataki and b.stan == "IDZ", f"stan={b.stan}")

# 2. potwor ucieka z widoku (zostaje na liscie stworow, ale poza ekranem)
s = Swiat(); s.stwory = [{"id": 10, "nazwa": "Rat", "gracz": False, "x": 103, "y": 100, "z": 7, "hp": 30}]
b = zrob(s, trasa(), okrazenia=1); s.zabija = False
b.tick(); b.tick()
s.stwory[0]["x"] = 118   # znika z widoku
n = len(s.ataki)
b.tick(); b.tick()
sprawdz("2 uciekajacy potwor: brak lootu i atakow poza widokiem, wraca do trasy",
        b.lootlog == [] and b.cel is None and b.stan == "IDZ" and len(s.ataki) == n, f"stan={b.stan}")
s.stwory.clear(); s.stwory.append({"id": 13, "nazwa": "Rat", "gracz": False, "x": s.poz[0]+3, "y": 100, "z": 7, "hp": 50})
b.tick(); zw = (s.stwory[0]["x"], 100, 7); s.stwory.clear(); bieg(b, s, 10)
sprawdz("2b zniknal z listy na ekranie (odl 3) = zgon: podejscie i loot", b.lootlog == [zw] and b.cel is None, f"loot={b.lootlog}")

# 2c. zabity z odleglosci 3 (na liscie z hp 0): podchodzi do zwlok i lootuje obok
s = Swiat(); s.stwory = [{"id": 14, "nazwa": "Rat", "gracz": False, "x": 104, "y": 100, "z": 7, "hp": 40}]
b = zrob(s, trasa(), okrazenia=1)
b.tick()   # atak -> hp -10, cel 4 pola dalej (gracz zdazyl zrobic 1 krok)
b.tick()
sprawdz("2c zgon z daleka: podejscie i loot obok zwlok", b.lootlog == [(104,100,7)], f"loot={b.lootlog} gracz={getattr(s,'loot_gracz',None)}")

# 2d. po wygasnieciu ignorowania nie ma spamu atakow co tick
s = Swiat(); s.stwory = [{"id": 15, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1); s.zabija = False
b.ignorowane[15] = -1.0   # wygasle ignorowanie
t0 = s.t
for _ in range(20): b.tick()
sprawdz("2d wygasle ignorowanie: ataki w odstepach >= 2 s", len(s.ataki) <= (s.t - t0) / 2 + 1, f"ataki={len(s.ataki)} t={s.t - t0:.1f}")

# 3. niskie HP: ucieczka wstecz + alarm, potem wznowienie
s = Swiat(poz=(105,100,7), hp=100); s.stwory = [{"id": 11, "nazwa": "Troll", "gracz": False, "x": 106, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1); b.idx = 6
s.zabija = False
b.tick(); s.hp = 30
x0 = s.poz[0]
for _ in range(6): b.tick()
sprawdz("3 niskie HP: stan UCIECZKA, alarm, cofa sie, brak nowych atakow",
        b.stan == "UCIECZKA" and len(s.alarmy) == 1 and s.poz[0] < x0, f"poz={s.poz} alarmy={s.alarmy}")
n = len(s.ataki)
for _ in range(10): b.tick()
sprawdz("3b w ucieczce nie atakuje", len(s.ataki) == n)
s.stwory.clear(); s.hp = 80
b.tick(); b.tick()
sprawdz("3c po regeneracji (>=70%) wraca do IDZ", b.stan == "IDZ" and not b.ucieczka, f"stan={b.stan}")

# 4. gracz na ekranie: zwykły nie zatrzymuje, groźny (czaszka / GM) i --stop-przy-graczach tak
def gracz_obcy(nazwa="Obcy", **kw):
    return {"id": 12, "nazwa": nazwa, "gracz": True, "x": 104, "y": 100, "z": 7, "hp": 100, **kw}
s = Swiat(); s.stwory = [gracz_obcy()]
b = zrob(s, trasa(), okrazenia=1)
p0 = list(s.poz); n0 = len(cavelog)
for _ in range(5): b.tick()
sprawdz("4 zwykły obcy gracz: gramy dalej, bez alarmu", b.stan != "GRACZ" and s.poz != p0 and not s.alarmy, f"stan={b.stan} alarmy={s.alarmy}")
wpisy = [l for l in cavelog[n0:] if "Gracz w pobliżu: Obcy" in l]
sprawdz("4a zwykły gracz: jeden wpis info w logu (bez [GRACZ])", len(wpisy) == 1 and not any("[GRACZ]" in l for l in cavelog[n0:]), wpisy)
s = Swiat(); s.stwory = [gracz_obcy(czaszka=1)]
b = zrob(s, trasa(), okrazenia=1)
for _ in range(2): b.tick()
sprawdz("4d0 gracz z czaszką przy PK_OBRONA=1: ucieczka PK (obrona_pk), nie pauza GRACZ", b.pk_stan == "UCIECZKA" and b.stan != "GRACZ",
        f"pk={b.pk_stan} stan={b.stan}")
cavebot.PK_OBRONA = 0      # dawne zachowanie (stan GRACZ) zostaje dla PK_OBRONA=0; obrona PK ma własny test_obrona_pk.py
s = Swiat(); s.stwory = [gracz_obcy(czaszka=1)]
b = zrob(s, trasa(), okrazenia=1); p0 = list(s.poz)
for _ in range(5): b.tick()
sprawdz("4d gracz z czaszką: pauza + alarm, bez ruchu i klawiszy", b.stan == "GRACZ" and s.poz == p0 and len(s.alarmy) == 1 and not s.ataki, f"alarmy={s.alarmy}")
s.stwory.clear(); b.tick(); b.tick()
sprawdz("4b gracz zniknal -> idzie", b.stan == "IDZ" and s.poz != p0)
cavebot.PK_OBRONA = 1
s = Swiat(); s.stwory = [gracz_obcy("GM Janusz")]
b = zrob(s, trasa(), okrazenia=1); p0 = list(s.poz)
for _ in range(3): b.tick()
sprawdz("4e nick GM: pauza + alarm", b.stan == "GRACZ" and s.poz == p0 and len(s.alarmy) == 1, f"alarmy={s.alarmy}")
s = Swiat(); s.stwory = [gracz_obcy()]
b = zrob(s, trasa(), okrazenia=1, stop_przy_graczach=True); p0 = list(s.poz)
for _ in range(3): b.tick()
sprawdz("4f --stop-przy-graczach: zwykły gracz zatrzymuje jak dawniej", b.stan == "GRACZ" and s.poz == p0 and len(s.alarmy) == 1, f"alarmy={s.alarmy}")
s = Swiat(); s.stwory = [gracz_obcy(czaszka=1)]
b = zrob(s, trasa(), okrazenia=1, zatrzymaj_przy_graczu=False); b.tick(); b.tick()
sprawdz("4c --ignoruj-graczy (nawet czaszka)", s.poz != [100,100,7] and not s.alarmy)

# 5. glod
s = Swiat(hp=60); b = zrob(s, trasa(), czas_s=500, jedzenie="F1")
for _ in range(600):
    b.tick()
    if s.klawisze: break
sprawdz("5 glod: po 30 s bez wzrostu HP wciska F1", s.klawisze == ["F1"] and s.t >= 30, f"t={s.t:.0f} klawisze={s.klawisze}")
s = Swiat(hp=60); b = zrob(s, trasa(), czas_s=500, jedzenie="F1")
for i in range(150):
    if i % 20 == 0: s.hp += 1   # HP rosnie -> nie jest glodny
    b.tick()
sprawdz("5b rosnace HP = brak jedzenia", s.klawisze == [], f"t={s.t:.0f}")
s = Swiat(hp=60); b = zrob(s, trasa(), czas_s=500)
for _ in range(400): b.tick()
sprawdz("5c brak klawisza: tylko log, bez klawiszy", s.klawisze == [])

# 6. okrazenia i czas
s = Swiat(); b = zrob(s, trasa(), okrazenia=2)
n = bieg(b, s, 500)
sprawdz("6 2 okrazenia konczy petle", b.okrazenie == 2 and n < 500, f"okrazenie={b.okrazenie} ticki={n}")
s = Swiat(); b = zrob(s, trasa(), czas_s=5)
n = bieg(b, s, 500)
sprawdz("6b limit czasu", n < 500 and s.t >= 5)
s = Swiat(); b = zrob(s, trasa(), okrazenia=1, czas_s=10000)
n = bieg(b, s, 500)
sprawdz("6c okrazenia + czas: konczy po okrazeniu", b.okrazenie == 1 and n < 500, f"ticki={n}")

# 7. chwilowy blad odczytu nie zabija bota; seria bledow konczy
s = Swiat(); b = zrob(s, trasa(), okrazenia=1)
stary = s.zapytaj; licznik = [0]
def zawodny(z):
    licznik[0] += 1
    if licznik[0] in (3, 4): raise ConnectionRefusedError("rdzen sie przeladowuje")
    return stary(z)
b.zapytaj = zawodny
b.uruchom()
sprawdz("7 chwilowe bledy: bot konczy okrazenie", b.okrazenie == 1)
s = Swiat(); b = zrob(s, trasa(), okrazenia=1)
def zawsze(z): raise ConnectionRefusedError("brak gniazda")
b.zapytaj = zawsze
b.uruchom()
sprawdz("7b ciagle bledy: konczy po limicie", b.okrazenie == 0)


# 1e. ramka ataku widoczna -> brak ponownego Alt+klik (ponowny klik wyłączyłby atak)
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 21, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa()); b.czy_atakowany = lambda stwor, gracz: True
bieg(b, s, 60)
sprawdz("1e ramka widoczna: tylko pierwszy atak", len(s.ataki) == 1, f"ataki={len(s.ataki)}")


# 8. losowe dodatki
cavebot.REAKCJA = LOSOWE["REAKCJA"]
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 31, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa()); s.zabija = False; start = s.t
bieg(b, s, 20)
sprawdz("8a czas reakcji przed pierwszym atakiem", s.ataki and 0.3 <= s.ataki[0][1] - start <= 1.6, f"atak po {s.ataki[0][1]-start if s.ataki else None}")
cavebot.REAKCJA = (0.0, 0.0)

cavebot.DRUGI_CEL = 1.0
s = Swiat(poz=(100,100,7), hp=100)
s.stwory = [{"id": 41, "nazwa": "Rat", "gracz": False, "x": 102, "y": 100, "z": 7, "hp": 100},
            {"id": 42, "nazwa": "Rat", "gracz": False, "x": 104, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa()); s.zabija = False
bieg(b, s, 1)       # jeden obieg: potem bot podchodzi i świeży obok przejmuje cel (Zmiana celu, test 11d)
sprawdz("8b drugi najbliższy cel", b.cel and b.cel["id"] == 42, f"cel={b.cel and b.cel['id']}")
cavebot.DRUGI_CEL = 0.0

cavebot.ROZRZUT_PROGU = 5.0
progi = set()
for i in range(30):
    s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 50+i, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
    b = zrob(s, trasa(), prog_hp=40); s.zabija = False; b.tick(); progi.add(round(b.prog_aktualny, 1))
sprawdz("8c rozrzut progu ucieczki ±5", len(progi) > 5 and min(progi) >= 35 and max(progi) <= 45, f"{min(progi)}..{max(progi)}")
cavebot.ROZRZUT_PROGU = 0.0

cavebot.ODWROCENIE_TRASY = 1.0
s = Swiat(poz=(100,100,7), hp=100); pkt = trasa()
b = zrob(s, pkt, okrazenia=1)
bieg(b, s, 200)
sprawdz("8d odwrócenie trasy po okrążeniu", b.punkty[0] == tuple(pkt[-1]), f"pierwszy={b.punkty[0]}")
cavebot.ODWROCENIE_TRASY = 0.0

s = Swiat(poz=(100,100,7), hp=100)
b = zrob(s, trasa(), czas_s=100000); b.przerwa_od = s.t
bieg(b, s, 2)
sprawdz("8e przerwa od gry", b.przerwa_do is not None and b.stan == "PRZERWA", f"stan={b.stan}")


# 9. uciekający słaby cel: goni od razu, także poza ekranem (do 10 pól), bez klikania poza widokiem
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 61, "nazwa": "Rat", "gracz": False, "x": 103, "y": 100, "z": 7, "hp": 20}]
b = zrob(s, trasa()); s.zabija = False
bieg(b, s, 3)
sprawdz("9a słaby cel 3 pola dalej: goni bez czekania", s.poz[0] >= 101, f"poz={s.poz}")
s.stwory[0]["x"] = s.poz[0] + 9; n = len(s.ataki)
bieg(b, s, 2)
sprawdz("9b cel poza ekranem (9 pól): pogoń bez klików", b.stan == "POGON" and len(s.ataki) == n and b.cel is not None, f"stan={b.stan}")


# 1g. domyślnie: od razu podchodzi do zdrowego potwora
s = Swiat(); s.stwory = [{"id": 8, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1); s.zabija = False
bieg(b, s, 4)
sprawdz("1g domyślnie podchodzi bez czekania", s.poz[0] >= 102 and len(s.ataki) >= 1, f"poz={s.poz}")


# 10. tryb chodzenia kliknięciem (atrapa: klik przenosi postać o 1 pole w stronę klikniętego pola na każdy sen)
def zrob_klik(s, punkty, **kw):
    b = zrob(s, punkty, **kw)
    s.kliki = []
    s.klik_cel = None
    def klik(dx, dy):
        s.kliki.append((dx, dy)); s.klik_cel = (s.poz[0] + dx, s.poz[1] + dy)
    stary_spij = s.spij
    def spij(d):
        stary_spij(d)
        if s.klik_cel and d >= 0.08:
            x, y, z = s.poz; cx, cy = s.klik_cel
            if (x, y) != (cx, cy):
                x += (cx > x) - (cx < x); y += (cy > y) - (cy < y) if x == cx else 0
                s.poz = [x, y, z]
    b.spij = spij
    b.klik = klik
    def klawisz(k):                   # strzałka: krok o 1 pole od razu, przerywa marsz po kliku
        s.klawisze.append(k)
        if k in bot.KIERUNKI:
            d = bot.KIERUNKI[k]; s.klik_cel = None
            s.poz[0] += d[0]; s.poz[1] += d[1]
    b.postac.klawisz = klawisz
    return b
s = Swiat(poz=(100,100,7), hp=100)
b = zrob_klik(s, [(100+i,100,7) for i in range(1,21)], okrazenia=1)
bieg(b, s, 40)
sprawdz("10a trasa kliknięciem: postęp i mało klików", s.poz[0] >= 110 and 1 <= len(s.kliki) <= 12, f"poz={s.poz} kliki={len(s.kliki)}")
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 71, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 100}]
b = zrob_klik(s, trasa()); s.zabija = False
bieg(b, s, 12)
sprawdz("10b podejście do potwora kliknięciem w pole przy nim", s.poz[0] == 104 and s.kliki and s.kliki[0] == (4, 0), f"poz={s.poz} kliki={s.kliki[:3]}")

# 11. nowe zachowania ruchu i walki
def szczur(i, x, hp=100, y=100, nazwa="Rat"):
    return {"id": i, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": 7, "hp": hp}

# 11a. ucz_uciekania: szczur obok, przy HP 25% oddala się -> próg zbliża się do 25; bez zapisu pliku
plik_przed = cavebot.PLIK_UCIEKANIA.exists()
s = Swiat(); s.stwory = [szczur(81, 101)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); b.tick()
s.stwory[0]["hp"] = 25; b.tick()
s.stwory[0]["x"] = 102; b.tick()
prog = b.prog_uciekania("Rat")
sprawdz("11a ucz_uciekania: próg Rat zbliża się do 25, brak zapisu pliku w trybie testowym",
        b.klik is None and 25 <= prog < 30 and plik_przed == cavebot.PLIK_UCIEKANIA.exists(), f"prog={prog}")
sprawdz("11a' inny gatunek zostaje na domyślnym", b.prog_uciekania("Troll") == cavebot.HP_UCIEKAJACEGO)

# 11b. CZUJNOSC: HP blisko progu -> krótsze pauzy niż przy HP 100%
def suma_snu(hp):
    s = Swiat(); s.stwory = [szczur(82, 101, hp=hp)]
    b = zrob(s, trasa()); s.zabija = False
    sny = []
    stary = s.spij
    def spij(d): sny.append(d); stary(d)
    b.spij = spij
    for _ in range(3): b.tick()      # pierwszy atak i ustalenie celu
    sny.clear()
    for _ in range(20): b.tick()
    return sum(sny) / 20
sen_pelne, sen_blisko = suma_snu(100), suma_snu(cavebot.PROG_UCIEKANIA_DOMYSLNY["rat"] + 5)
sprawdz("11b CZUJNOSC: blisko progu śpi krócej na obieg", sen_blisko < sen_pelne / 2, f"HP100={sen_pelne:.3f}s blisko={sen_blisko:.3f}s")

# 11c. uciekający cel 2 pola dalej -> pościg strzałką na pole drogi przy nim (od naszej strony),
#      bez kliku (klik prowadził o 1-2 pola co ~3 s)
s = Swiat(); s.stwory = [szczur(83, 102, hp=20)]
b = zrob_klik(s, trasa()); s.zabija = False
b.tick()
sprawdz("11c uciekający cel: strzałka Right na pole przy nim (101,100), bez kliku",
        s.klawisze == ["Right"] and not s.kliki and s.poz[:2] == [101, 100], f"klawisze={s.klawisze} kliki={s.kliki[:3]} poz={s.poz}")
sprawdz("11c' przewidz_ucieczke po przekątnej",
        cavebot.Cavebot.przewidz_ucieczke({"x": 98, "y": 103}, (100, 100)) == (97, 104))

# 11d. potwór obok ma pierwszeństwo przed dalszym celem
s = Swiat(); s.stwory = [szczur(84, 104)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); b.tick()
pierwszy = b.cel and b.cel["id"]
s.stwory.append(szczur(85, s.poz[0] + 1))
b.tick(); b.tick()
sprawdz("11d potwór obok przejmuje cel (Zmiana celu)", pierwszy == 84 and b.cel and b.cel["id"] == 85, f"przed={pierwszy} po={b.cel and b.cel['id']}")

# 11e. POGON_LIMIT: cel ucieka, dystans się nie zmniejsza -> odpuszczony i ignorowany 20 s
s = Swiat(); s.stwory = [szczur(86, 103)]
b = zrob(s, trasa()); s.zabija = False
t0 = s.t; odpuszczony = None
for i in range(300):
    if odpuszczony is None: s.stwory[0]["x"] = s.poz[0] + 3
    b.tick()
    if b.ignorowane.get(86) and odpuszczony is None:
        odpuszczony = s.t - t0; t_ign = s.t; do = b.ignorowane[86]
        break
sprawdz("11e POGON_LIMIT: odpuszcza po > limicie, ignoruje 20 s",
        odpuszczony is not None and cavebot.POGON_LIMIT < odpuszczony < cavebot.POGON_LIMIT + 3
        and abs((do - t_ign) - cavebot.POGON_IGNOROWANIE) < 1.5 and b.cel is None,
        f"po {odpuszczony} s, do-teraz={do - t_ign if odpuszczony else None}")
n = len(s.ataki)
for _ in range(10): b.tick()
sprawdz("11e' ignorowany cel nie jest ponownie atakowany", len(s.ataki) == n and b.cel is None, f"ataki {n}->{len(s.ataki)}")

# 11f. trasa kliknięciem bez ruchu postaci -> po KLIK_BEZ_RUCHU fallback strzałką
s = Swiat(); b = zrob_klik(s, [(100+i,100,7) for i in range(1,21)])
s.klik_cel = None
b.klik = lambda dx, dy: s.kliki.append((dx, dy))     # klik nic nie rusza
b.spij = s.spij                                         # bez poruszania postaci przy śnie
t0 = s.t; kroki_przed = None
for i in range(60):
    x0 = s.poz[0]; b.tick()
    if s.poz[0] != x0 and kroki_przed is None: kroki_przed = (s.t - t0, len(s.kliki))
sprawdz("11f klik bez ruchu: po ~KLIK_BEZ_RUCHU fallback strzałką, postać rusza",
        kroki_przed is not None and kroki_przed[0] >= cavebot.KLIK_BEZ_RUCHU and kroki_przed[0] < 4 and s.poz[0] > 100,
        f"pierwszy krok po {kroki_przed}, poz={s.poz}, kliki={len(s.kliki)}")



# 1h. po ciemku (ramka nieznana): potwór obok bez spadku HP -> ponowny atak co >= 6 s, nie częściej
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 81, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa()); s.zabija = False; b.czy_atakowany = lambda stwor, gracz: None
bieg(b, s, 120)
odstepy = [y[1] - x[1] for x, y in zip(s.ataki, s.ataki[1:])]
sprawdz("1h ciemno: ponowienia przy zacięciu, nie częściej niż co 6 s", len(s.ataki) >= 2 and all(o >= 6.0 for o in odstepy), f"ataki={len(s.ataki)} odstepy={[round(o,1) for o in odstepy[:4]]}")


# 12. labirynt: droga po znanych polach (kręty korytarz szerokości 1 pola, reszta to ściany)
from collections import deque as _deque
cavebot.PLIK_ZNANYCH = Path_scratch = __import__("pathlib").Path(__file__).resolve().parent / "znane_pola_test.json"
WOLNE = [(98,100),(99,100),(100,100),(100,101),(101,101),(102,101),(103,101),(103,102),(103,103),
         (104,103),(105,103),(106,103),(107,103),(107,104),(107,105),(108,105),(109,105)]
WOLNE_Z = [(x, y, 7) for x, y in WOLNE]
def labirynt(s, wolne=WOLNE):
    """Swiat ze ścianami: ruch tylko po polach `wolne`, nie przez pola zajęte przez stwory."""
    s.wolne = set(wolne); s.w_sciane = []; s.odbicia = 0
    def zajete(): return {(m["x"], m["y"]) for m in s.stwory if m.get("hp", 100) > 0}
    s.zajete = zajete
def zrob_lab(s, punkty, klik=True, **kw):
    labirynt(s)
    b = (zrob_klik if klik else zrob)(s, punkty, **kw)
    s.kliki = getattr(s, "kliki", []); s.klik_cel = None
    def krok(k):                      # strzałka: ściana / stwór = brak ruchu
        d = bot.KIERUNKI[k]; s.t += 0.2
        nowa = (s.poz[0] + d[0], s.poz[1] + d[1])
        if nowa not in s.wolne or nowa in s.zajete():
            s.odbicia += 1; return None
        s.poz[0], s.poz[1] = nowa; return tuple(s.poz)
    b.postac.krok = krok
    s.klawisze_lab = []
    def klawisz(k):                   # strzałka w trybie kliku: jak krok, przerywa marsz po kliku
        s.klawisze.append(k)
        if k in bot.KIERUNKI:
            s.klik_cel = None
            krok(k); s.t -= 0.2       # czas kroku liczy pauza bota po strzałce
    b.postac.klawisz = klawisz
    if klik:
        def klik_f(dx, dy):           # klient: klik w ścianę albo bez drogi = postać stoi
            c = (s.poz[0] + dx, s.poz[1] + dy)
            s.kliki.append((dx, dy))
            if c not in s.wolne: s.w_sciane.append(c)
            s.klik_cel = c
        def spij(d):
            s.t += d
            if s.klik_cel and d >= 0.08 and tuple(s.poz[:2]) != s.klik_cel:
                start = tuple(s.poz[:2]); skad = {start: None}; q = _deque([start]); blok = s.zajete()
                while q:
                    a = q.popleft()
                    if a == s.klik_cel: break
                    for n in ((a[0]+1,a[1]),(a[0]-1,a[1]),(a[0],a[1]+1),(a[0],a[1]-1)):
                        if n in s.wolne and n not in blok and n not in skad:
                            skad[n] = a; q.append(n)
                if s.klik_cel in skad:
                    n = s.klik_cel
                    while skad[n] != start: n = skad[n]
                    s.poz[0], s.poz[1] = n
        b.klik = klik_f; b.spij = spij
    return b
def obok(s, m): return max(abs(s.poz[0]-m["x"]), abs(s.poz[1]-m["y"])) <= 1
def do_celu(b, s, m, ticki):
    for i in range(ticki):
        b.tick()
        if obok(s, m): return i + 1
    return None

# 12a. przypadek z logu: pole "od naszej strony" po prostej to ściana -> klik po drodze
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(91, 102, y=101)]
b = zrob_lab(s, WOLNE_Z); s.zabija = False
s.stwory[0]["x"], s.stwory[0]["y"] = 103, 101          # stoi 3 pola dalej, za zakrętem
n = do_celu(b, s, s.stwory[0], 30)
sprawdz("12a zdrowy potwór za zakrętem: dochodzi kliknięciem, bez klików w ściany",
        n is not None and n <= 10 and not s.w_sciane, f"obiegi={n} poz={s.poz} kliki={s.kliki} w_sciane={s.w_sciane}")

# 12b. uciekający (HP 20) daleko za dwoma zakrętami, poza ekranem częściowo -> pogoń po drodze
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(92, 107, hp=20, y=104)]
b = zrob_lab(s, WOLNE_Z); s.zabija = False
n = do_celu(b, s, s.stwory[0], 40)
sprawdz("12b uciekający za dwoma zakrętami: dochodzi po drodze, bez klików w ściany",
        n is not None and n <= 20 and not s.w_sciane and s.odbicia == 0, f"obiegi={n} poz={s.poz} kliki={s.kliki} w_sciane={s.w_sciane}")

# 12c. POGON poza ekranem (dx 9): cel osiągalny tylko krętą drogą
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(93, 104, hp=20, y=103)]
b = zrob_lab(s, WOLNE_Z); s.zabija = False
b.tick(); s.stwory[0]["x"], s.stwory[0]["y"] = 109, 105   # uciekł poza ekran (dx 9)
s.kliki.clear(); s.klik_cel = None; b.tick(); stan = b.stan
n = do_celu(b, s, s.stwory[0], 60)
sprawdz("12c POGON poza ekranem: dochodzi po drodze strzałkami, bez klików poza widokiem i w ściany",
        stan == "POGON" and n is not None and not s.w_sciane and s.odbicia == 0
        and all(abs(k[0]) <= 6 and abs(k[1]) <= 4 for k in s.kliki),
        f"stan0={stan} obiegi={n} poz={s.poz} kliki={s.kliki[:4]} w_sciane={s.w_sciane} odbicia={s.odbicia}")

# 12d. strzałki (bez kliku): krok po kroku po drodze, bez odbijania się od ścian
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(94, 106, y=103)]
b = zrob_lab(s, WOLNE_Z, klik=False); s.zabija = False
n = do_celu(b, s, s.stwory[0], 40)
sprawdz("12d strzałkami: dochodzi bez uderzeń w ściany", n is not None and s.odbicia == 0,
        f"obiegi={n} poz={s.poz} odbicia={s.odbicia}")

# 12e. brak znanej drogi -> dawne zachowanie: pole przy potworze od naszej strony
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(95, 102, y=98)]
b = zrob_lab(s, WOLNE_Z); s.zabija = False
b.tick(); b.tick()
sprawdz("12e brak drogi: fallback klik w pole od naszej strony (1,-1)",
        b.droga((100,100,7), (102,98)) is None and s.kliki and s.kliki[0] == (1, -1), f"kliki={s.kliki[:3]}")

# 12f. droga omija stwora stojącego w korytarzu (zajęte pole) -> brak drogi zamiast drogi przez niego
s = Swiat(poz=(100,100,7)); b = zrob_lab(s, WOLNE_Z)
d_wolna = b.droga((100,100,7), (105,103))
d_zajeta = b.droga((100,100,7), (105,103), zajete=[(102,101)])
sprawdz("12f droga: najkrótsza po znanych polach, omija zajęte", d_wolna and d_wolna[0] == (100,101,7)
        and d_wolna[-1] == (104,103,7) and len(d_wolna) == 7 and d_zajeta is None, f"{d_wolna} / {d_zajeta}")

# 12g. limit BFS: daleki cel w dużym znanym obszarze -> None szybko
s = Swiat(poz=(0,0,7)); b = zrob(s, trasa())
b.znane |= {(x, y, 7) for x in range(-40, 41) for y in range(-40, 41)}
sprawdz("12g limit BFS (DROGA_LIMIT) dla dalekiego celu", b.droga((0,0,7), (39,39)) is None and b.droga((0,0,7), (5,3)) is not None)

# 12h. podejście do zwłok za zakrętem (zbierz_loot) po drodze
s = Swiat(poz=(100,100,7)); b = zrob_lab(s, WOLNE_Z)
b.zbierz_loot((104,103,7))
sprawdz("12h loot za zakrętem: podchodzi po drodze i lootuje", b.lootlog == [(104,103,7)] and not s.w_sciane,
        f"loot={b.lootlog} poz={s.poz} w_sciane={s.w_sciane}")

# 12i. mapa znanych pól: trasy z pliku + pozycje widziane w tick(); bez zapisu w testach
s = Swiat(poz=(200,200,7)); b = zrob(s, trasa(), okrazenia=1)
bieg(b, s, 3)
kanaly = (32032,32150,11) in b.znane
d = b.droga((32032,32150,11), (32034,32151)) if kanaly else None
sprawdz("12i znane pola: trasy/*.json wczytane, pozycja gracza dopisana, brak pliku w teście",
        kanaly and (200,200,7) in b.znane and not cavebot.PLIK_ZNANYCH.exists() and not b.zapis_znanych,
        f"kanaly={kanaly} znane={len(b.znane)}")
sprawdz("12j przypadek z logu na mapie kanałów: droga omija ścianę (32033,32150)",
        d is not None and (32033,32150,11) not in d and max(abs(d[-1][0]-32034), abs(d[-1][1]-32151)) <= 1, f"droga={d}")

# 12k. przejście po skosie (zapisane w trasie między ścianami): klik je zna, strzałki nie
s = Swiat(poz=(0,0,7)); b = zrob(s, trasa())
b.znane |= {(0,0,7), (1,1,7), (2,1,7), (3,1,7), (4,1,7)}
d_skos = b.droga((0,0,7), (5,1)); d_prosto = b.droga((0,0,7), (5,1), skosy=False)
b.znane |= {(x, y, 7) for x in (0, 1) for y in range(10, 14)}   # korytarz 2 pola szeroki
d_l = b.droga((0,10,7), (0,14))
sprawdz("12k skos tylko gdy potrzebny: droga po skosie, bez skosów brak; w korytarzu 2-polowym prosto",
        d_skos == [(1,1,7),(2,1,7),(3,1,7),(4,1,7)] and d_prosto is None and d_l == [(0,11,7),(0,12,7),(0,13,7)],
        f"{d_skos} / {d_prosto} / {d_l}")

# 12l. inne piętro: znane pola z innego z się nie liczą
s = Swiat(poz=(100,100,6)); b = zrob_lab(s, WOLNE_Z)
sprawdz("12l droga tylko po polach tego samego piętra", b.droga((100,100,6), (105,103)) is None
        and b.droga((100,100,7), (105,103)) is not None)

# 12m. własna postać na starej liście stworów (pętla zbierz_loot) nie blokuje drogi
s = Swiat(poz=(100,100,7)); b = zrob_lab(s, WOLNE_Z)
b.ostatnie_stwory = [{"id": 1, "nazwa": b.postac.nazwa, "gracz": True, "x": 100, "y": 101, "z": 7, "hp": 100}]
b.zbierz_loot((104,103,7))
sprawdz("12m własna postać z listy stworów nie zajmuje pola", b.lootlog == [(104,103,7)] and not s.w_sciane,
        f"loot={b.lootlog} poz={s.poz} w_sciane={s.w_sciane}")

# 13. objazd: cel 3 pola w linii prostej, ale za ścianą; znana droga naokoło ~15 pól -> odpuszczony
OBJAZD = [(100, y) for y in range(100, 108)] + [(x, 107) for x in (101, 102)] + [(103, y) for y in range(107, 100, -1)]
OBJAZD_Z = [(x, y, 7) for x, y in OBJAZD]
for hp, opis in ((100, "zdrowy (klik)"), (20, "uciekający (strzałki)")):
    s = Swiat(poz=(100,100,7)); s.stwory = [szczur(101, 103, hp=hp)]
    b = zrob_lab(s, OBJAZD_Z); labirynt(s, OBJAZD); s.zabija = False
    d = b.droga((100,100,7), (103,100), [(103,100)], skosy=False)
    for i in range(6):
        b.tick()
        if b.ignorowane.get(101): break
    sprawdz(f"13a objazd ({opis}): droga {len(d) if d else d} pól do celu 3 pola dalej -> odpuszczony, bez ruchu w przeciwną stronę",
            d is not None and len(d) >= 14 and b.ignorowane.get(101) and b.cel is None
            and s.poz[:2] == [100, 100] and not s.kliki
            and all(k == "Right" for k in s.klawisze) and len(s.klawisze) <= 2,   # najwyżej próba W STRONĘ celu
            f"obiegi={i+1} poz={s.poz} kliki={s.kliki} klawisze={s.klawisze} ign={b.ignorowane}")
# objazd nie dotyczy lootu: do zwłok za ścianą idziemy naokoło
s = Swiat(poz=(100,100,7)); b = zrob_lab(s, OBJAZD_Z); labirynt(s, OBJAZD)
b.zbierz_loot((103,100,7))
sprawdz("13a' loot za ścianą: do zwłok idzie naokoło", b.lootlog == [(103,100,7)] and not s.w_sciane, f"loot={b.lootlog} poz={s.poz}")

# 13b. pościg strzałkami: stojący słaby cel - dystans maleje co obieg; uciekający - dogania
s = Swiat(); s.stwory = [szczur(102, 105, hp=20)]
b = zrob_klik(s, trasa()); s.zabija = False
odl = [b.dystans(s.poz, (105, 100))]
for _ in range(8):
    b.tick(); odl.append(b.dystans(s.poz, (105, 100)))
    if odl[-1] <= 1: break
sprawdz("13b pościg strzałkami: dystans maleje co obieg, bez klików",
        odl[-1] == 1 and all(y == x - 1 for x, y in zip(odl, odl[1:])) and not s.kliki
        and set(s.klawisze) == {"Right"}, f"odl={odl} kliki={s.kliki} klawisze={s.klawisze}")
s = Swiat(); s.stwory = [szczur(103, 104, hp=20)]
b = zrob_klik(s, trasa()); s.zabija = False
zrzuty = []; b.czy_atakowany = lambda stwor, gracz: zrzuty.append(s.t) or False
odl = []
for i in range(20):
    if i % 2 == 1 and s.stwory[0]["x"] < 110: s.stwory[0]["x"] += 1   # ucieka co drugi obieg
    odl.append(b.dystans(s.poz, (s.stwory[0]["x"], 100)))
    if odl[-1] <= 1: break
    b.tick()
sprawdz("13b' uciekający (krok co 2 obiegi): dystans nie rośnie, dogania bez klików",
        odl[-1] <= 1 and all(y <= x for x, y in zip(odl, odl[1:])) and not s.kliki, f"odl={odl} kliki={s.kliki}")

# 13c. daleki cel: jeden atak na start, potem bez ponowień i bez zrzutów ramki, dopóki nie stoi obok
# (zmiana celowa: uciekający 2<=odl<=6 dostaje ponowny Alt+klik co POSCIG_ATAK_CO s, gdy ramka mówi "brak ataku")
czasy = [t for _, t in s.ataki]
sprawdz("13c daleki uciekający cel: ponowny atak najczęściej co POSCIG_ATAK_CO s, ramka sprawdzana tylko przy próbie",
        len(s.ataki) >= 1 and all(b2 - a >= cavebot.POSCIG_ATAK_CO - 1e-6 for a, b2 in zip(czasy, czasy[1:]))
        and len(zrzuty) <= len(s.ataki) + 2, f"ataki={len(s.ataki)} zrzuty={len(zrzuty)} czasy={czasy}")
s = Swiat(); s.stwory = [szczur(104, 106)]
b = zrob(s, trasa()); s.zabija = False; b.czekaj = True
zrzuty = []; b.czy_atakowany = lambda stwor, gracz: zrzuty.append(s.t) or False
bieg(b, s, 30, lambda i: s.stwory[0].__setitem__("x", s.poz[0] + 6))   # zdrowy cel trzyma dystans
sprawdz("13c' daleki zdrowy cel (odl 6): 1 atak, 0 zrzutów ramki", len(s.ataki) == 1 and not zrzuty,
        f"ataki={len(s.ataki)} zrzuty={len(zrzuty)} poz={s.poz}")

# 14. sprawdzanie ataku z pamięci (pole "atakowany" w stwory, komenda cel_ataku), zrzut tylko w fallbacku
def zrob14(s, pole):
    s.stwory = [szczur(9, 101)]
    if pole is not None: s.stwory[0]["atakowany"] = pole
    b = zrob(s, trasa()); s.zabija = False
    zrzuty = []
    b._atakowany_ze_zrzutu = lambda stwor, gracz: zrzuty.append(s.t) or None
    b.czy_atakowany = b._atakowany_domyslny
    return b, zrzuty
s = Swiat(); b, zrzuty = zrob14(s, True)
bieg(b, s, 60)
sprawdz("14 flaga atakowany=True (po ciemku): 1 atak, bez ponowień i bez zrzutów",
        len(s.ataki) == 1 and not zrzuty, f"ataki={len(s.ataki)} zrzuty={len(zrzuty)}")
s = Swiat(); b, zrzuty = zrob14(s, False)
bieg(b, s, 12)
sprawdz("14b flaga atakowany=False: ponawia atak przed ZACIECIE_ATAKU, bez zrzutów",
        len(s.ataki) >= 2 and not zrzuty and s.ataki[1][1] - s.ataki[0][1] < cavebot.ZACIECIE_ATAKU,
        f"ataki={[round(a[1],1) for a in s.ataki]} zrzuty={len(zrzuty)}")
# bez pola w stwory (starszy rdzen): decyduje komenda cel_ataku
s = Swiat(); b, zrzuty = zrob14(s, None); m = s.stwory[0]
cel_id = [m["id"]]
def zap(z):
    if z["cmd"] == "cel_ataku": return {"id": cel_id[0]}
    return s.zapytaj(z)
b.zapytaj = zap
wyniki = []
for c in (m["id"], None, m["id"] + 1):
    cel_id[0] = c; wyniki.append(b._atakowany_domyslny(m, {"x": 100, "y": 100}))
sprawdz("14c bez pola: cel_ataku decyduje (nasz/brak/inny)", wyniki == [True, False, False] and not zrzuty,
        f"{wyniki} zrzuty={len(zrzuty)}")
# odczyt z pamięci zawodzi: fallback na zrzut (None po ciemku), ponowienie dopiero przy zacięciu
s = Swiat(); b, zrzuty = zrob14(s, None)
def zap_blad(z):
    if z["cmd"] == "cel_ataku": raise ConnectionError("brak gniazda")
    return s.zapytaj(z)
b.zapytaj = zap_blad
bieg(b, s, 80)
sprawdz("14d pamięć zawodzi -> zrzut (None) + ponowienie dopiero po ZACIECIE_ATAKU",
        zrzuty and len(s.ataki) >= 2 and s.ataki[1][1] - s.ataki[0][1] >= cavebot.ZACIECIE_ATAKU,
        f"ataki={[round(a[1],1) for a in s.ataki]} zrzuty={len(zrzuty)}")


# 15. cel ginie w ruchu: najpierw pole, na które wchodził, potem ostatnio widziane
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 91, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 30}]
b = zrob(s, trasa()); s.zabija = False
proby = []
def zbierz15(zwloki, gracz):
    proby.append(tuple(zwloki)); return "brak_okna" if len(proby) == 1 else "ok"
b.loot = types.SimpleNamespace(zbierz=zbierz15)
b.tick(); b.tick()
s.stwory[0]["y"] = 101; b.tick()          # krok w dół
s.stwory.clear(); bieg(b, s, 6)            # ginie (znika z listy na ekranie)
sprawdz("15 zgon w ruchu (LOOT_DYNAMICZNY=1): najpierw ostatnie widziane pole, potem poprzednie pole celu",
        proby[:2] == [(101, 101, 7), (101, 100, 7)], f"proby={proby}")
# 15b. dawne zachowanie (LOOT_DYNAMICZNY=0): najpierw pole w kierunku ruchu
cavebot.LOOT_DYNAMICZNY = 0
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 91, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 30}]
b = zrob(s, trasa()); s.zabija = False
proby = []
b.loot = types.SimpleNamespace(zbierz=zbierz15)
b.tick(); b.tick()
s.stwory[0]["y"] = 101; b.tick()
s.stwory.clear(); bieg(b, s, 6)
cavebot.LOOT_DYNAMICZNY = 1
sprawdz("15b zgon w ruchu (LOOT_DYNAMICZNY=0): najpierw pole w kierunku ruchu, potem ostatnie", proby[:2] == [(101, 102, 7), (101, 101, 7)], f"proby={proby}")


# 16. pełna mapa serwera (mapa.py): atrapa wstrzykiwana do Cavebot, potem prawdziwy plik
import mapa as _mapa_mod
class AtrapaMapy(_mapa_mod.Mapa):
    """Mapa jak z pliku OTMM: pola `wolne` przechodnie (flaga 1), `inne` {(x,y): flagi},
    reszta bloków 64x64, w których coś leży, to widziane ściany (5); poza blokami nic (0)."""
    def __init__(s, wolne, z=7, inne=None):
        s._dane, s._spis, s._bloki, s.wersja = b"", {}, {}, 1
        pola = {tuple(p[:2]): 1 for p in wolne}; pola.update(inne or {})
        for bx, by in {(x >> 6, y >> 6) for x, y in pola}:
            b = bytearray(bytes([5, 114, 0]) * 4096)
            for (x, y), f in pola.items():
                if (x >> 6, y >> 6) == (bx, by):
                    b[((y & 63) * 64 + (x & 63)) * 3] = f
            s._bloki[_mapa_mod._klucz_bloku(bx << 6, by << 6, z)] = bytes(b)
def sala(sciana_x, sciana_do_y, x=(98, 110), y=(95, 112)):
    """Sala ze ścianą w kolumnie sciana_x od góry sali do sciana_do_y (przejście niżej)."""
    return [(a, c) for a in range(x[0], x[1] + 1) for c in range(y[0], y[1] + 1)
            if not (a == sciana_x and c <= sciana_do_y)]
def zrob_mapa(s, wolne, swiat=None, **kw):
    """zrob_lab z atrapą pełnej mapy `wolne`; świat (ruch) wg `swiat` (domyślnie = mapa)."""
    b = zrob_lab(s, [(200 + i, 200, 7) for i in range(1, 11)], mapa=AtrapaMapy(wolne), **kw)   # trasa z dala od sali
    labirynt(s, swiat if swiat is not None else wolne)
    return b

# 16a. uciekający szczur 3 pola dalej za ścianą z przejściem: droga 12 pól (dawniej > 2*3+4 = objazd)
SALA12 = sala(102, 104)
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(161, 103, hp=20)]
b = zrob_mapa(s, SALA12); s.zabija = False
d = b.droga((100,100,7), (103,100), [(103,100)], skosy=False)
poza_znanymi = b._droga_znane((100,100,7), (103,100), [(103,100)], skosy=False) is None   # drogę zna tylko pełna mapa
n = do_celu(b, s, s.stwory[0], 40)
sprawdz("16a mapa: cel za ścianą z krótkim objazdem (12 pól przy 3 prosto) -> gonimy strzałkami po drodze",
        d is not None and len(d) == 12 and n is not None and not b.ignorowane and not s.kliki
        and s.odbicia == 0 and poza_znanymi,
        f"droga={d} poza={poza_znanymi} obiegi={n} poz={s.poz} ign={b.ignorowane} kliki={s.kliki} odbicia={s.odbicia}")

# 16b. ten sam układ, przejście daleko: droga 16 pól > 2*3+8 -> odpuszczony, bez ruchu
SALA16 = sala(102, 106)
for hp, opis in ((20, "uciekający"), (100, "zdrowy")):
    s = Swiat(poz=(100,100,7)); s.stwory = [szczur(162, 103, hp=hp)]
    b = zrob_mapa(s, SALA16); s.zabija = False
    d = b.droga((100,100,7), (103,100), [(103,100)], skosy=False)
    for i in range(6):
        b.tick()
        if b.ignorowane.get(162): break
    sprawdz(f"16b mapa: objazd 16 pól przy 3 prosto ({opis}) -> odpuszczony bez ruchu",
            d is not None and len(d) == 16 and b.ignorowane.get(162) and b.cel is None
            and s.poz[:2] == [100, 100] and not s.kliki and not s.klawisze and "16 pól" in b.ostatni_objazd,
            f"droga={len(d) if d else d} poz={s.poz} klawisze={s.klawisze} opis={b.ostatni_objazd!r}")

# 16c. brak drogi na mapie (cel w zamkniętej komorze) -> odpuszczony; do zwłok tam (loot) - bez objazdu, pole od naszej strony
KOMORA = [(a, c) for a in range(98, 111) for c in range(95, 112) if a != 102]
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(163, 104, hp=20)]
b = zrob_mapa(s, KOMORA); s.zabija = False
bieg(b, s, 4)
sprawdz("16c mapa: brak drogi -> odpuszczony (brak drogi w logu), bez ruchu",
        b.ignorowane.get(163) and s.poz[:2] == [100, 100] and "brak drogi" in b.ostatni_objazd, f"{b.ostatni_objazd!r} poz={s.poz}")

# 16d. self.sciany ważniejsze niż mapa: pole nauczone jako ściana omijamy, choć mapa mówi "przechodnie";
#      na polu przechodnim wg mapy nauka wygasa po SCIANA_WAZNA s, na polu nieznanym mapie - nie
KORYTARZ2 = [(a, c) for a in range(98, 111) for c in (100, 101)]
s = Swiat(poz=(100,100,7)); b = zrob_mapa(s, KORYTARZ2)
d0 = b.droga((100,100,7), (106,100), skosy=False)
b.sciany[(102,100,7)] = s.t
b.znane.add((120,100,7)); b.sciany[(120,100,7)] = s.t       # pole poza mapą, na którym stał gracz
d1 = b.droga((100,100,7), (106,100), skosy=False)
s.t += cavebot.SCIANA_WAZNA + 1
d2 = b.droga((100,100,7), (106,100), skosy=False)
sprawdz("16d sciany > mapa: nauczona ściana omijana, wygasa tylko na polu przechodnim wg mapy",
        d0 and (102,100,7) in d0 and d1 and (102,100,7) not in d1 and len(d1) == len(d0) + 1
        and d2 == d0 and (102,100,7) not in b.sciany and b.sciana((120,100,7)),
        f"d0={d0} d1={d1} d2={d2}")

# 16e. zamknięte drzwi (mapa: przechodnie, świat: nie) w pościgu strzałkami: uczy się ściany
#      dopiero po KROK_SCIANA s bez ruchu i obchodzi; pole, na którym stał cel, nie jest ścianą
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(164, 105, hp=20)]
b = zrob_mapa(s, KORYTARZ2, swiat=[p for p in KORYTARZ2 if p != (102, 100)]); s.zabija = False
n = do_celu(b, s, s.stwory[0], 40)
sprawdz("16e mapa nieaktualna (drzwi): ściana nauczona z nieudanego kroku, obchodzi i dogania",
        n is not None and list(b.sciany) == [(102,100,7)] and not b.ignorowane and s.odbicia == 1,
        f"obiegi={n} poz={s.poz} sciany={b.sciany} odbicia={s.odbicia}")
s = Swiat(poz=(100,100,7)); b = zrob_mapa(s, KORYTARZ2)
b.krok_prosto_ost = ((100,100,7), (101,100,7), s.t)
w1 = b.sprawdz_krok((100,100,7), [], (105,100))               # krok jeszcze może trwać
s.t += cavebot.KROK_SCIANA
w2 = b.sprawdz_krok((100,100,7), [(101,100)], (105,100))      # stał tam stwór: nie ściana
b.krok_prosto_ost = ((100,100,7), (101,100,7), s.t); s.t += cavebot.KROK_SCIANA
w3 = b.sprawdz_krok((100,100,7), [], (101,100))               # stał tam cel: nie ściana
sprawdz("16e' nauka ścian: nie w trakcie kroku, nie na polu stwora ani celu",
        w1 is True and w2 is False and w3 is False and not b.sciany, f"{w1} {w2} {w3} {b.sciany}")

# 16f. pola poza blokami mapy: znane pola (stał tam gracz) liczą się jak przechodnie - droga jak bez mapy;
#      cel na polu nieznanym ani mapie, ani nam -> dawne zachowanie (klik w pole od naszej strony)
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(165, 103, y=101)]
b = zrob_lab(s, WOLNE_Z, mapa=AtrapaMapy([(5000, 5000)])); s.zabija = False
dz = b.droga((100,100,7), (105,103))
n = do_celu(b, s, s.stwory[0], 30)
sprawdz("16f mapa nie zna pól, my tak: droga po znanych polach jak bez mapy",
        b.mapa_zna((100,100,7), (105,103)) and dz == b._droga_znane((100,100,7), (105,103))
        and n is not None and not s.w_sciane, f"droga={dz} obiegi={n}")
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(166, 102, y=98)]
b = zrob_lab(s, WOLNE_Z, mapa=AtrapaMapy([(5000, 5000)])); s.zabija = False
b.tick(); b.tick()
sprawdz("16f' cel na polu nieznanym mapie ani nam: dawne zachowanie (klik (1,-1) od naszej strony)",
        not b.mapa_zna((100,100,7), (102,98)) and s.kliki and s.kliki[0] == (1, -1) and not b.ignorowane,
        f"kliki={s.kliki[:3]} ign={b.ignorowane}")

# 16g. brak pliku mapy / plik uszkodzony -> self.mapa None (dawne zachowanie), bez wyjątku
_plik, _wsp = _mapa_mod.PLIK_MAPY, _mapa_mod._mapa
try:
    _mapa_mod._mapa = None; _mapa_mod.PLIK_MAPY = cavebot.Path("/nie/ma/takiego/map74.otmm")
    brak = cavebot.Cavebot._wczytaj_mape()
    zly = cavebot.Path(__file__).resolve().parent / "zla_mapa_test.otmm"; zly.write_bytes(b"XXXX" + bytes(20))
    _mapa_mod._mapa = None; _mapa_mod.PLIK_MAPY = zly
    uszk = cavebot.Cavebot._wczytaj_mape()
    zly.unlink()
finally:
    _mapa_mod.PLIK_MAPY, _mapa_mod._mapa = _plik, _wsp
s = Swiat(); b = zrob(s, trasa())
sprawdz("16g brak/uszkodzony plik mapy -> None; w testach z atrapą ataku mapa tylko wstrzyknięta",
        brak is None and uszk is None and b.mapa is None, f"{brak} {uszk} {b.mapa}")

# 17. prawdziwy plik mapy: przypadki z logów 11.10 (pozycje z linii debug)
if _mapa_mod.PLIK_MAPY.is_file():
    import time as _time
    PRAWDZIWA = _mapa_mod.Mapa()
    KANALY = [tuple(p) for p in __import__("json").loads((cavebot.KATALOG_TRAS / "kanaly2.json").read_text())]
    PRZYPADKI = [((32046,32157,11), (32047,32154), "01:19:24 dawniej droga 83"),
                 ((32039,32157,11), (32034,32155), "01:19:44 dawniej 42"),
                 ((32038,32156,11), (32033,32153), "01:32:58 dawniej 40"),
                 ((32021,32159,11), (32013,32161), "01:22:14 dawniej 46"),
                 ((32055,32155,11), (32058,32154), "01:28:12 krok prosto w ściany"),
                 ((32055,32155,11), (32052,32158), "01:29:21 krok prosto w ściany"),
                 ((32055,32155,11), (32059,32157), "01:29:30 krok prosto w ściany")]
    for poz, rat, opis in PRZYPADKI:
        s = Swiat(poz=poz); s.stwory = [dict(szczur(170, rat[0], hp=20, y=rat[1]), z=poz[2])]
        b = zrob_klik(s, KANALY, mapa=PRAWDZIWA); s.zabija = False
        b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
        t0 = _time.perf_counter()
        d = b.droga(poz, rat, [rat], skosy=False)
        ms = (_time.perf_counter() - t0) * 1000
        prosto = b.dystans(poz, rat)
        w = b.podejdz(rat, poz, pilne=True, natychmiast=True)
        sprawdz(f"17 mapa z pliku, {opis}: droga krótka, pościg strzałką zamiast odpuszczenia",
                d is not None and len(d) <= 2 * prosto + cavebot.MAPA_OBJAZD and w is True
                and len(s.klawisze) == 1 and not s.kliki and tuple(s.poz) == d[0],
                f"droga={len(d) if d else d} prosto={prosto} {ms:.1f} ms wynik={w} klawisze={s.klawisze}")
    # ściana z kanałów (32033,32150) nadal omijana
    s = Swiat(poz=(32032,32150,11)); b = zrob_klik(s, KANALY, mapa=PRAWDZIWA)
    d = b.droga((32032,32150,11), (32034,32150), [(32034,32150)], skosy=False)
    sprawdz("17b mapa z pliku: ściana (32033,32150) omijana", d and (32033,32150,11) not in d, f"droga={d}")
    # prawdziwy objazd: (32011,32155) -> (32007,32158), 4 pola prosto, droga 22 -> odpuszczony
    s = Swiat(poz=(32011,32155,11)); s.stwory = [dict(szczur(171, 32007, hp=20, y=32158), z=11)]
    b = zrob_klik(s, KANALY, mapa=PRAWDZIWA); s.zabija = False
    b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
    w = b.podejdz((32007,32158), (32011,32155,11), pilne=True, natychmiast=True)
    sprawdz("17c mapa z pliku: prawdziwy objazd (22 pola przy 4 prosto) -> odpuszczony",
            w is None and not s.klawisze and "22 pól" in b.ostatni_objazd, f"wynik={w} {b.ostatni_objazd!r}")
    # pełny pościg w świecie z prawdziwej mapy (ruch tylko po przechodnich polach): przypadek 01:32:58
    poz, rat = (32038,32156,11), (32033,32153)
    swiat = [(x, y) for x in range(poz[0] - 15, poz[0] + 16) for y in range(poz[1] - 15, poz[1] + 16)
             if PRAWDZIWA.przechodnie(x, y, 11) and not PRAWDZIWA.schody_lub_dziura(x, y, 11)]
    s = Swiat(poz=poz); s.stwory = [dict(szczur(172, rat[0], hp=20, y=rat[1]), z=11)]
    b = zrob_lab(s, KANALY, mapa=PRAWDZIWA); labirynt(s, swiat); s.zabija = False
    n = do_celu(b, s, s.stwory[0], 40)
    sprawdz("17d pościg w świecie z prawdziwej mapy (01:32:58): dogania bez odpuszczania i bez uderzeń w ściany",
            n is not None and not b.ignorowane and s.odbicia == 0 and not s.w_sciane and not b.sciany,
            f"obiegi={n} poz={s.poz} ign={b.ignorowane} odbicia={s.odbicia}")
    # wydajność: 200 dróg z pościgu (pary z kanaly2 do 10 pól) na prawdziwej mapie
    import random as _r
    rr = _r.Random(7); czasy = []
    s = Swiat(poz=KANALY[0]); b = zrob_klik(s, KANALY, mapa=PRAWDZIWA)
    b.droga(KANALY[0], KANALY[1], skosy=False)    # rozgrzewka: jednorazowy skan schodów (zakaz zmiany piętra)
    for _ in range(200):
        a = rr.choice(KANALY); c = rr.choice([p for p in KANALY if p[2] == a[2] and 2 <= b.dystans(a, p) <= 10])
        t0 = _time.perf_counter(); b.droga(a, c, [c[:2]], skosy=False); czasy.append(_time.perf_counter() - t0)
    czasy.sort()
    sprawdz("17e wydajność drogi na pełnej mapie: mediana < 10 ms, max < 100 ms (obciążona maszyna)",
            czasy[100] < 0.010 and czasy[-1] < 0.100, f"mediana {czasy[100]*1000:.1f} ms, p95 {czasy[190]*1000:.1f} ms, max {czasy[-1]*1000:.1f} ms")
else:
    sprawdz("17 prawdziwy plik mapy dostępny", False, str(_mapa_mod.PLIK_MAPY))



# 18c. cel blisko, ale bez drogi (za ścianą): nie odpuszczamy (ping-pong), czekamy z trwającym atakiem
cavebot.CZEKAJ_BLISKO = 5
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(101, 103)]
b = zrob_lab(s, OBJAZD_Z); labirynt(s, OBJAZD); s.zabija = False
for i in range(6): b.tick()
# ZMIANA CELOWA (czekanie wg DROGI, nie linii prostej): dawniej cel 3 pola za ścianą nie był odpuszczany
# (czekanie); teraz droga naokoło ~16 pól > NIEOSIAGALNY_DROGA -> odpuszczony z flagą "nieosiągalny"
sprawdz("18c cel 3 pola za ścianą (droga ~16): odpuszczony z flagą nieosiągalny, bez czekania i bez ataku",
        b.ignorowane.get(101) and b.nieosiagalne.get(101) == 3 and b.cel is None and len(s.ataki) <= 1,
        f"ign={b.ignorowane} nieos={b.nieosiagalne} cel={b.cel} ataki={s.ataki}")

# 18. loot: nie stajemy na zwłokach
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
b.zbierz_loot((100,100,7))
sprawdz("18a stoimy na zwłokach: schodzimy na sąsiednie pole przed Ctrl+klikiem",
        b.lootlog == [(100,100,7)] and tuple(s.loot_gracz[:2]) != (100,100), f"gracz={getattr(s, 'loot_gracz', None)} poz={s.poz}")
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
b.zbierz_loot((104,100,7))
sprawdz("18b podejście do zwłok kończy się obok, nie na ich polu",
        b.lootlog == [(104,100,7)] and tuple(s.loot_gracz[:2]) != (104,100) and max(abs(s.loot_gracz[0]-104), abs(s.loot_gracz[1]-100)) <= 1,
        f"gracz={getattr(s, 'loot_gracz', None)}")

# 19. blokady (stwór, fałszywa ściana) nie zamykają korytarza, który mapa uważa za przejezdny
if PRAWDZIWA is not None:
    s = Swiat(poz=(32055,32159,11)); b = zrob_lab(s, KANALY, mapa=PRAWDZIWA)
    b.sciany[(32055,32158,11)] = b.zegar()
    d = b.droga((32055,32159,11), (32058,32157), [(32056,32157)], skosy=False)
    sprawdz("19a fałszywa ściana + stwór w wąskim korytarzu: droga po samej mapie istnieje", d is not None and b.droga_bez_blokad == 1, f"d={d}")

# 20. loot nie rusza przy żywym potworze blisko; odłożone zwłoki czekają
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(300, 103)]
b = zrob(s, trasa()); b.ignorowane[300] = 10 ** 9; b.zwloki_czekajace = [((101,100,7), s.t)]
bieg(b, s, 3)
sprawdz("20a LOOT_DYNAMICZNY=1: żywy (ignorowany) szczur 3 pola dalej nie wstrzymuje lootu zwłok obok", b.lootlog == [(101,100,7)], f"loot={b.lootlog}")
cavebot.LOOT_DYNAMICZNY = 0
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(300, 103)]
b = zrob(s, trasa()); b.ignorowane[300] = 10 ** 9; b.zwloki_czekajace = [((101,100,7), s.t)]
bieg(b, s, 3)
cavebot.LOOT_DYNAMICZNY = 1
sprawdz("20a2 LOOT_DYNAMICZNY=0: dawne zachowanie, szczur 3 pola dalej wstrzymuje loot", not b.lootlog, f"loot={b.lootlog}")
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa()); b.zwloki_czekajace = [((101,100,7), s.t)]
bieg(b, s, 3)
sprawdz("20b bez żywych potworów odłożone zwłoki są zbierane", b.lootlog == [(101,100,7)], f"loot={b.lootlog}")

# 21: Ctrl+klik wprowadził nas na zwłoki -> schodzimy na sąsiednie pole i otwieramy ponownie
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa()); b.zwloki_czekajace = [((101,100,7), s.t)]
_zb = b.loot.zbierz
def _wchodzi(zw, gr):
    if len(b.lootlog) == 0:
        b.lootlog.append(zw); s.poz = [101,100,7]
        return "brak_okna"
    s.stoi_na_zwlokach = s.poz[:2] == (101,100)
    return _zb(zw, gr)
b.loot.zbierz = _wchodzi
bieg(b, s, 4)
sprawdz("21 stoję na zwłokach po nieudanym otwarciu -> zejście i ponowny loot",
        len(b.lootlog) == 2 and s.poz[:2] != (101,100) and not s.stoi_na_zwlokach, f"loot={b.lootlog} poz={s.poz}")

# 22. droga/czekanie/ściany (log 12:18-12:19: szczur 2 pola obok, droga 50 przez fałszywą ścianę)
POKOJ = [(a, c) for a in range(98, 111) for c in range(95, 113)]
# 22a. fałszywa ściana (cała kolumna x=101 do y=108) + szczur 2 pola obok: droga po blokadach to objazd
#      ~20 pól (> 2*2+8), po samej mapie 2 pola -> bot bierze krótszą i podchodzi, nie odpuszcza
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(400, 102)]
b = zrob_mapa(s, POKOJ); s.zabija = False
for yy in range(95, 109): b.sciany[(101, yy, 7)] = s.t
d = b.droga((100,100,7), (102,100), [(102,100)], skosy=False)
n = do_celu(b, s, s.stwory[0], 12)
sprawdz("22a fałszywa ściana + szczur obok: droga krótka (po mapie), podchodzi, nie odpuszcza",
        d is not None and len(d) <= 3 and b.droga_bez_blokad >= 1 and n is not None and not b.ignorowane,
        f"droga={d} dbb={b.droga_bez_blokad} obiegi={n} poz={s.poz} ign={b.ignorowane}")
s = Swiat(poz=(100,100,7)); b = zrob_mapa(s, POKOJ)
d0 = b.droga((100,100,7), (102,100), [(102,100)], skosy=False)
sprawdz("22a' bez blokad: droga po mapie 1-2 pola, licznik fallbacku 0", d0 is not None and len(d0) <= 2 and b.droga_bez_blokad == 0, f"{d0}")
SCIANA_PRAW = sala(101, 108, x=(98, 110), y=(95, 112))
s = Swiat(poz=(100,100,7)); b = zrob_mapa(s, SCIANA_PRAW)
d1 = b.droga((100,100,7), (102,100), [(102,100)], skosy=False)
sprawdz("22a'' prawdziwa ściana w mapie: droga naokoło (> 2*prosto+8) zostaje, bez fallbacku",
        d1 is not None and len(d1) > 2 * 2 + cavebot.MAPA_OBJAZD and b.droga_bez_blokad == 0, f"{len(d1) if d1 else d1} {b.droga_bez_blokad}")

# 22b. czekanie tylko przy krótkiej DRODZE: szczur 2 pola za prawdziwą długą ścianą -> nie czekamy,
#      ignorowanie 90 s z flagą "nieosiągalny" (CZEKAJ_BLISKO=5 jak w produkcji)
DLUGA = sala(101, 140, x=(98, 110), y=(95, 145))
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(401, 102)]
b = zrob_mapa(s, DLUGA); s.zabija = False
d = b.droga((100,100,7), (102,100), [(102,100)], skosy=False)
for i in range(6):
    b.tick()
    if b.ignorowane.get(401): break
sprawdz("22b droga > 15 pól do szczura 2 pola dalej: bez czekania, ignorowanie 90 s z flagą nieosiągalny",
        d is not None and len(d) > cavebot.NIEOSIAGALNY_DROGA and cavebot.CZEKAJ_BLISKO >= 2
        and b.ignorowane.get(401) and b.nieosiagalne.get(401) == 2 and b.cel is None and len(s.ataki) <= 1
        and s.poz[:2] == [100, 100],
        f"droga={len(d) if d else d} ign={b.ignorowane} nieos={b.nieosiagalne} cel={b.cel} poz={s.poz}")

# 22c. flaga nieosiągalny: zbliżenie o 1 pole jej nie kasuje (ani IGNOROWANIE_BLISKO), o 2 albo obok - tak
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
poz = (100,100,7)
b.ignorowane[500] = s.t + 90; b.nieosiagalne[500] = 4
def jest(x, i=500):
    return [m["id"] for m in b.kandydaci([szczur(i, x)], poz)] == [i]
w4, w3 = jest(104), jest(103)
sprawdz("22c nieosiągalny: 4 i 3 pola (zbliżenie o 1) nadal ignorowany, flaga zostaje",
        not w4 and not w3 and 500 in b.nieosiagalne and b.ignorowane.get(500), f"{w4} {w3} {b.nieosiagalne}")
w2 = jest(102)
sprawdz("22c' zbliżenie o 2 pola zdejmuje ignorowanie i flagę", w2 and 500 not in b.nieosiagalne and 500 not in b.ignorowane)
b.ignorowane[501] = s.t + 90; b.nieosiagalne[501] = 2
sprawdz("22c'' stwór obok (gryzie) zawsze wraca do kandydatów", jest(101, 501) and 501 not in b.nieosiagalne)
b.ignorowane[502] = s.t + 90
sprawdz("22c''' zwykłe ignorowanie: 3 pola = znów brany (IGNOROWANIE_BLISKO)", jest(103, 502))
b.ignorowane[503] = s.t + 90; b.nieosiagalne[503] = 6; s.t += 91
sprawdz("22c4 po OBJAZD_IGNOROWANIE ignorowanie i flaga wygasają", jest(106, 503) and 503 not in b.nieosiagalne)

# 22d. ściana nie zapisuje się, gdy chwilę wcześniej stał tam stwór (uciekł z pola)
s = Swiat(poz=(100,100,7)); b = zrob_mapa(s, KORYTARZ2)
poz = (100,100,7)
b.odnotuj_stwory([szczur(600, 101)], poz)                        # tick N: szczur na (101,100)
b.krok_prosto_ost = (poz, (101,100,7), s.t); s.t += cavebot.KROK_SCIANA
w = b.sprawdz_krok(poz, [], (105,100))                           # tick N+1: pole puste (uciekł)
sprawdz("22d pole po uciekającym stworze (widzianym < SCIANA_STWOR s temu) nie jest ścianą", w is False and not b.sciany, f"{b.sciany}")
b.krok_prosto_ost = (poz, (101,100,7), s.t); s.t += cavebot.SCIANA_STWOR + cavebot.KROK_SCIANA
b.sprawdz_krok(poz, [], (105,100))
sprawdz("22d' stwór dawno temu: ściana jak dotąd", list(b.sciany) == [(101,100,7)], f"{b.sciany}")
s.t += cavebot.SCIANA_WAZNA + 0.1
sprawdz("22d'' ściana na polu przechodnim wg mapy wygasa po SCIANA_WAZNA (5-8 s)",
        5 <= cavebot.SCIANA_WAZNA <= 8 and not b.sciana((101,100,7)))


# 24. szybkość reakcji i dobijanie (pomiar telemetrii 11:58-12:25)
sprawdz("24a stałe: reakcja, pościg, loot, próg ucieczki",
        LOSOWE["REAKCJA"] == (0.15, 0.45) and cavebot.POGON_LIMIT == 14.0 and cavebot.POSCIG_OKNO == 3.0
        and cavebot.LOOT_PO_WALCE == 8 and cavebot.PROG_UCIEKANIA_MIN == 25 and cavebot.LOOT_BLOK_MAX == 8)
s = Swiat(); b = zrob(s, trasa())
b.progi_uciekania["rat"] = 15
sprawdz("24a' próg uciekania nigdy poniżej PROG_UCIEKANIA_MIN (też stary zapis 15/20)",
        b.prog_uciekania("Rat") == cavebot.PROG_UCIEKANIA_MIN)

# 24b. dobijanie 12% HP w zasięgu 6 przed świeżym celem (stary klucz: 6+0.5 > 2+4)
s = Swiat(); s.stwory = [szczur(901, 106, hp=12), szczur(902, 102, hp=100)]
b = zrob(s, trasa()); s.zabija = False
b.tick()
sprawdz("24b wybór celu: ranny 12% w odl 6 przed świeżym w odl 2", b.cel and b.cel["id"] == 901, f"cel={b.cel}")
# 24b'. świeży stoi obok, HP gracza nie spada: ranny cel (odl 4) zostaje
s = Swiat(); s.stwory = [szczur(903, 104, hp=12)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(904, 101, hp=100)); b.tick()
sprawdz("24b' świeży obok bez spadku HP gracza: dobijamy rannego (zasięg 6)", b.cel and b.cel["id"] == 903, f"cel={b.cel}")
n_log = len(cavelog); s.hp = 70; b.tick()
sprawdz("24b'' świeży gryzie (HP gracza spada): zmiana celu", any("Zmiana celu" in l for l in cavelog[n_log:]),
        f"cel={b.cel}")

# 24c. pościg: cel 15% HP trzyma dystans 5 - nie odpuszczamy przed POGON_TWARDY, potem tak
s = Swiat(); s.stwory = [szczur(905, 105, hp=15)]
b = zrob(s, trasa()); s.zabija = False
t0 = s.t; wczesnie = False; odpuszczony = None
for i in range(800):
    s.stwory[0]["x"] = s.poz[0] + 5
    b.tick()
    if b.ignorowane.get(905):
        odpuszczony = s.t - t0; break
sprawdz("24c pościg 15% HP w odl 5: odpuszczony dopiero po POGON_TWARDY (25 s), nie po 14",
        odpuszczony is not None and cavebot.POGON_TWARDY <= odpuszczony < cavebot.POGON_TWARDY + 3,
        f"po {odpuszczony} s")

# 24d. objazd: umierający cel za ścianą ignorowany tylko OBJAZD_DOBICIE s, zdrowy 90 s
for hp, oczek in ((12, cavebot.OBJAZD_DOBICIE), (100, cavebot.OBJAZD_IGNOROWANIE)):
    s = Swiat(poz=(100,100,7)); s.stwory = [szczur(906, 103, hp=hp)]
    b = zrob_lab(s, OBJAZD_Z); labirynt(s, OBJAZD); s.zabija = False
    for i in range(6):
        b.tick()
        if b.ignorowane.get(906): break
    ile = b.ignorowane.get(906, 0) - s.t
    sprawdz(f"24d objazd hp {hp}%: ignorowanie ~{oczek} s", abs(ile - oczek) < 2, f"ile={ile:.1f}")

# 24e. jedzenie: brak jedzenia nie jest ponawiane przez JEDZENIE_PONOW s; przy celu <=3 nie jemy
wywolania = []
def zjedz_pusty(log=print): wywolania.append(s.t); return []
s = Swiat(hp=50); b = zrob_klik(s, trasa())
b.loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=zjedz_pusty)
b.tick(); s.t += 40; b.tick()
n1 = len(wywolania); s.t += 40; b.tick(); n2 = len(wywolania)
s.t += cavebot.JEDZENIE_PONOW; b.tick(); n3 = len(wywolania)
sprawdz("24e brak jedzenia: jedna próba, potem cisza przez JEDZENIE_PONOW s, potem znów", (n1, n2, n3) == (1, 1, 2), f"{n1} {n2} {n3}")
wywolania.clear()
s = Swiat(hp=50); s.stwory = [szczur(907, 102)]
b = zrob_klik(s, trasa()); s.zabija = False
b.loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=print: wywolania.append(s.t) or ["ser"])
b.tick(); s.t += 40; b.tick()
w_walce = len(wywolania)
s.stwory = []; b.tick(); b.tick(); b.tick()
sprawdz("24e' przy celu w odl <= 3 nie jemy; po walce tak", w_walce == 0 and len(wywolania) >= 1, f"walka={w_walce} po={len(wywolania)}")

# 24f. ślepe pauzy na trasie wyłączone, gdy potwór w odl <= 3
cavebot.PAUZA_DLUGA = (1.0, 3.0, 8.0); cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
s = Swiat(); b = zrob(s, trasa())
b.ostatnie_stwory = [szczur(908, 102)]; t0 = s.t; b.idz(); bez = s.t - t0
b.ostatnie_stwory = []; t0 = s.t; b.idz(); z_pauza = s.t - t0
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
sprawdz("24f PAUZA_DLUGA wyłączona przy mobie <= 3 (jest bez moba)", bez < 2.5 and z_pauza >= 3.0, f"bez={bez:.1f} z={z_pauza:.1f}")

# 24g. loot: żywy potwór podchodzi w trakcie zbierania -> przerwanie z hakiem PRZERWIJ, zwłoki odłożone
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
def zbierz_z_gryzoniem(zwloki, gracz):
    s.stwory.append(szczur(909, 101, hp=100)); s.t += 1.0
    return "przerwany" if b.loot.PRZERWIJ() else "ok"
b.loot = types.SimpleNamespace(zbierz=zbierz_z_gryzoniem)
w = b.zbierz_loot((100,101,7))
sprawdz("24g loot: potwór obok w trakcie zbierania przerywa, zwłoki wracają na listę, hak zdjęty",
        w == "przerwany" and any(z == (100,101,7) for z, _ in b.zwloki_czekajace) and b.loot.PRZERWIJ is None,
        f"w={w} czekajace={b.zwloki_czekajace}")

# 24h. powód odmowy drogi: pola blokujące w jednej linii
s = Swiat(); b = zrob(s, trasa())
b.sciany[(100,99,7)] = s.t
opis = b._powod_braku_drogi((100,100,7), (105,100,7), [(101,100)])
sprawdz("24h powód odmowy drogi wskazuje stwora i nauczoną ścianę", "stwór" in opis and "[pola:" in opis, opis)
b.sciany[(100,101,7)] = s.t
sprawdz("24h' ściana nauczona w opisie", "ściana (nauczona)" in b._powod_braku_drogi((100,100,7), (100,95,7), []))

# 24i. pościg uciekającego z odl 2 po skosie: klik zamiast strzałki
s = Swiat(); s.stwory = [szczur(910, 102, y=102, hp=20)]
b = zrob_klik(s, trasa()); s.zabija = False
b.znane.clear(); b.znane.update({(100,100,7), (101,101,7)})
b.tick(); b.tick()
sprawdz("24i pościg po skosie (odl 2): klik (1,1), bez strzałki", (1,1) in s.kliki and not s.klawisze, f"kliki={s.kliki} klaw={s.klawisze}")

# 24j. po Escape (zatrzymaj_klik) atak jest ponawiany od razu
s = Swiat(); s.stwory = [szczur(911, 101, hp=100)]
b = zrob_klik(s, trasa()); s.zabija = False
b.tick(); n = len(s.ataki)
b.klik_cel = (105,100); b.klik_czas = s.t; s.t += 0.5
b.tick()
sprawdz("24j po zatrzymaj_klik (Escape) atak ponowiony od razu", "Escape" in s.klawisze and len(s.ataki) > n,
        f"klaw={s.klawisze} ataki {n}->{len(s.ataki)}")

# 25. utknięcie na trasie (log 11.10 12:26-12:36): kieszeń x=32018 y=32138..32141, wejście od zachodu
if _mapa_mod.PLIK_MAPY.is_file():
    MAPA25 = _mapa_mod.Mapa()
    WOLNE25 = [(x, y) for x in range(32000, 32070) for y in range(32128, 32170)
               if MAPA25.flagi(x, y, 11) & 1 and MAPA25.przechodnie(x, y, 11) is not False]
    TRASA25 = [tuple(p) for p in __import__("json").loads((cavebot.KATALOG_TRAS / "kanaly2.json").read_text())]
    def swiat25(klik, wylacz_c=False, poz=(32018, 32140, 11), idx=71):
        s = Swiat(poz=poz); s.t = 0.0
        b = zrob_lab(s, TRASA25, klik=klik, mapa=MAPA25, okrazenia=1)
        s.wolne = set(WOLNE25); b.idx = idx
        b.znane |= {(x, y, 11) for x, y in WOLNE25}
        if wylacz_c: b._droga_trasy = lambda poz, cel: None
        return s, b
    def idz25(s, b, sekundy, trasa=None):
        pozycje = []; idx0 = b.idx
        for _ in range(20000):
            if s.t >= sekundy or not b.tick(): break
            pozycje.append(tuple(s.poz))
        return pozycje

    # 25a. kierunki w krok_do: Left nie jest już nigdy ostatni, gdy to jedyne wyjście z kieszeni
    for klik in (False, True):
        s, b = swiat25(klik)
        cavelog.clear()
        poz = idz25(s, b, 12)
        wyszla = any(p[0] <= 32017 for p in poz)
        sprawdz(f"25a kieszeń, klik={klik}: bot wychodzi z kieszeni (A* po trasie / krok Left)",
                wyszla and poz[-1] != (32018, 32140, 11), f"poz={poz[:6]} ... {poz[-1]} klaw={s.klawisze[:6]} kliki={getattr(s,'kliki',[])[:4]}")

    # 25b. sam krok_do (C wyłączone): zachłanny krok z kieszeni nie wraca na pole, z którego przyszliśmy
    s, b = swiat25(False, wylacz_c=True)
    poz = idz25(s, b, 8)
    sprawdz("25b krok_do bez A*: wychodzi z kieszeni (Left), nie oscyluje 2 polami",
            any(p[0] <= 32017 for p in poz), f"poz={poz[:8]} klaw={s.klawisze[:8]}")

    # 25c. oscylacja 2 pól (zachłanny krok bez A* i bez zabezpieczenia B): wykrycie A po ~27 s -> idx przeskakuje
    for klik in (False, True):
        s, b = swiat25(klik, wylacz_c=True)
        b.krok_do = lambda cel, s=s, b=b: (s.klawisze.append("Down" if s.poz[1] == 32140 else "Up"),
                                            s.poz.__setitem__(1, 32141 if s.poz[1] == 32140 else 32140),
                                            setattr(s, "t", s.t + 0.2), True)[-1]
        b.klik = None if not klik else b.klik
        cavelog.clear()
        idx0 = b.idx; t0 = s.t; zdarzenie = []
        class Tele:
            def zdarzenie(self, typ, **d): zdarzenie.append((typ, d)); return d
            def probka(self, *a): return None
        b.tele = Tele()
        pol = set(); t_utk = None
        for i in range(400):
            b.tick(); pol.add(tuple(s.poz))
            if b.idx != idx0 and t_utk is None:
                t_utk = s.t - t0
            if t_utk is not None: break
        sprawdz(f"25c oscylacja 2 pól (klik={klik}): utknięcie po 25-35 s, idx -> najbliższy po drodze, log+telemetria",
                t_utk is not None and 25 <= t_utk <= 35 and b.idx != idx0 and len(pol) <= 4
                and any("utknięcie, wracam na trasę do punktu" in l for l in cavelog)
                and zdarzenie and zdarzenie[0][0] == "utkniecie_trasa" and b.utkniecia_trasy == 1,
                f"t={t_utk} idx {idx0}->{b.idx} pola={sorted(pol)} zd={zdarzenie[:1]} log={cavelog[-2:]}")
        # najbliższy po drodze: sprawdzamy niezależnie, że nie istnieje punkt trasy z krótszą drogą
        ref = min((len(MAPA25.droga((32018, s.poz[1], 11), p[:2], dlugosc=0) or [0] * 999), k)
                  for k, p in enumerate(TRASA25) if p[2] == 11 and max(abs(p[0]-32018), abs(p[1]-s.poz[1])) <= 30)
        d_wyb = MAPA25.droga((32018, s.poz[1], 11), TRASA25[b.idx][:2], dlugosc=0)
        sprawdz(f"25c' wybrany punkt jest najbliższy po drodze (klik={klik})",
                d_wyb is not None and len(d_wyb) <= ref[0] + 0, f"wybrany idx={b.idx} droga={len(d_wyb) if d_wyb else None} ref={ref}")

    # 25d. po utknięciu pełny bieg: postać wychodzi z kieszeni i dochodzi do punktu (idx rośnie)
    s, b = swiat25(True)
    idz25(s, b, 120)
    sprawdz("25d pełny bieg 120 s od kieszeni: idx się zmienia, postać poza kieszenią",
            b.idx != 71 and tuple(s.poz[:2]) not in {(32018, y) for y in range(32138, 32142)},
            f"idx={b.idx} poz={s.poz}")

    # 25e. wykrycie utknięcia nie reaguje na normalny marsz (idx rośnie, różne pola)
    s, b = swiat25(True, poz=(32013, 32146, 11), idx=10)
    n0 = b.utkniecia_trasy
    idz25(s, b, 90)
    sprawdz("25e normalny marsz po trasie nie jest utknięciem", b.utkniecia_trasy == n0 and b.idx > 10,
            f"utkniecia={b.utkniecia_trasy} idx={b.idx} poz={s.poz}")


# 26. uciekający cel (hp <= próg+10 albo <= 30%): pościg poza DOBICIE_ZASIEG, twardy limit, blokada przez świeżego
sprawdz("26a stałe: zasięg 10, twardy 40, ignorowanie krótkie",
        cavebot.DOBICIE_ZASIEG_UCIEKAJACY == 10 and cavebot.POGON_TWARDY == 40.0 and cavebot.POGON_IGNOROWANIE_DOBICIE <= 10)
# 26b. szczur 10% HP ucieka do odl 8 (poza ekranem), bot go goni (zasięg > starego 6) i dobija, gdy się zatrzyma
s = Swiat(); s.stwory = [szczur(950, 105, hp=10)]
b = zrob(s, trasa()); s.zabija = True
b.tick()      # cel wzięty na ekranie, potem ucieka poza ekran
t0 = s.t; ign = False; zabity = False
for i in range(400):
    m = [x for x in s.stwory if x["id"] == 950]
    if not m: zabity = True; break
    if s.t - t0 < 25: m[0]["x"] = s.poz[0] + 8       # ucieka, trzymając dystans 8
    b.tick()
    if b.ignorowane.get(950): ign = True; break
    s.stwory[:] = [x for x in s.stwory if x["hp"] > 0]
sprawdz("26b uciekający szczur 10% w odl 8: goniony i dobity, nie odpuszczony", zabity and not ign, f"zabity={zabity} ign={ign} t={s.t - t0:.0f}")
# 26c. nie zbliża się, ale bot idzie po drodze: nie odpuszcza przed twardym limitem (40 s dla <= 20% HP)
s = Swiat(); s.stwory = [szczur(951, 105, hp=10)]
b = zrob(s, trasa()); s.zabija = False
b.tick()
t0 = s.t; odpuszczony = None; do = 0
for i in range(1500):
    s.poz[0] += 1                      # bot idzie (strzałki w atrapie nie przesuwają postaci)
    s.stwory[0]["x"] = s.poz[0] + 8
    b.tick()
    if b.ignorowane.get(951): odpuszczony = s.t - t0; do = b.ignorowane[951]; break
sprawdz("26c bot się zbliża po drodze (cel trzyma dystans 8): odpuszcza dopiero po twardym limicie 40 s",
        odpuszczony is not None and cavebot.POGON_TWARDY <= odpuszczony < cavebot.POGON_TWARDY + 4, f"po {odpuszczony}")
sprawdz("26c' po odpuszczeniu ignorowanie krótkie (<= 10 s), nie 20/90 s",
        odpuszczony is not None and do - s.t <= cavebot.POGON_IGNOROWANIE_DOBICIE + 0.5, f"do-teraz={do - s.t:.1f}")
# 26d. ocena postępu: bot stoi (brak ruchu) >= POGON_LIMIT = odpuszcza; bot się rusza = nie; przerwa (jedzenie) nie liczy się
s = Swiat(); b = zrob(s, trasa())
cel = {"id": 960, "nazwa": "Rat", "hp": 10}
b.pogon_odl, b.pogon_postep, b.pogon_tick_ost = 5, 100.0, 100.0
powod = None
for t in range(101, 117):
    b.ruch_czas = 90.0                      # stoi
    powod = b.ocen_pogon(cel, 5, t)
sprawdz("26d bot stoi 14+ s bez zbliżenia: odpuszcza (brak postępu)", powod and "nie zbliżam" in powod, f"{powod}")
b.pogon_odl, b.pogon_postep, b.pogon_tick_ost = 5, 100.0, 100.0
b.pogon_uciek = (960, 100.0)
powod = None
for t in (105, 110, 115, 120, 125, 130):
    b.ruch_czas = t - 0.5                    # idzie
    powod = b.ocen_pogon(cel, 6, t)
    if t == 110: b.pogon_tick_ost = 109.0
sprawdz("26d2 bot idzie (cel o 1 dalej niż minimum): brak odpuszczenia", powod is None, f"{powod}")
b.pogon_odl, b.pogon_postep, b.pogon_tick_ost = 5, 100.0, 100.0
b.pogon_uciek = (960, 100.0)
b.ruch_czas = 90.0
r1 = b.ocen_pogon(cel, 5, 110.0)                 # 10 s bez ruchu: jeszcze nie
r2 = b.ocen_pogon(cel, 5, 120.0)                 # luka 10 s (jedzenie): nie liczy się
sprawdz("26d3 przerwa w pościgu (jedzenie/loot) nie liczy się do braku postępu", r1 is None and r2 is None, f"{r1} {r2}")
# 26e. świeży szczur obok blokuje drogę, bot stoi > BLOKADA_STOI: bijemy świeżego (nie stoimy 26 s)
s = Swiat(); s.stwory = [szczur(970, 104, hp=12)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(971, s.poz[0] + 1, hp=100))
b.tick()
c1 = b.cel and b.cel["id"]
b.ruch_czas = s.t - cavebot.BLOKADA_STOI - 1; b.ruch_poz = tuple(s.poz)
b.pogon_postep = s.t - cavebot.BLOKADA_STOI - 1; b.obok_od = {971: s.t - cavebot.BLOKADA_STOI - 1}
n_log = len(cavelog); b.tick()
sprawdz("26e dobijanie trwa, dopóki bot się rusza; po BLOKADA_STOI bez ruchu - Zmiana celu na blokującego",
        c1 == 970 and any("Zmiana celu" in l for l in cavelog[n_log:]), f"cel przed={c1} po={b.cel}")
# 26f. ponawianie ataku: tylko po 2 odczytach False, min POSCIG_ATAK_CO od kliku; nigdy gdy cel obok; weryfikacja po kliku
s = Swiat(); s.stwory = [szczur(980, 105, hp=10)]
b = zrob(s, trasa()); s.zabija = False
b.czy_atakowany = lambda st, g: False
c = dict(s.stwory[0]); poz = tuple(s.poz)
b.atak_czas = float("-inf")
r1 = b.ponow_atak(c, poz); n1 = len(s.ataki)
r2 = b.ponow_atak(c, poz); n2 = len(s.ataki)
# (zmiana celowa: weryfikacja nie blokuje 0,35 s, tylko czyta flagę w następnym obrocie, >= POSCIG_ATAK_WERYF_MIN po kliku)
sprawdz("26f pierwszy odczyt False: bez kliku; drugi: klik (bez blokującej weryfikacji)",
        r1 is False and n1 == 0 and r2 is True and n2 == 1, f"r1={r1} n1={n1} r2={r2} n2={n2}")
s.t += 0.1; r2b = b.ponow_atak(c, poz)
sprawdz("26f1 flaga za wcześnie (< WERYF_MIN po kliku): jeszcze bez cofnięcia", r2b is False and len(s.ataki) == 1)
s.t += 0.3; r2c = b.ponow_atak(c, poz)
sprawdz("26f1b następny obrót: flaga nadal False = jeden klik cofający", r2c is True and len(s.ataki) == 2, f"ataki={len(s.ataki)}")
r3 = b.ponow_atak(c, poz); r4 = b.ponow_atak(c, poz)
sprawdz("26f2 po nieudanej weryfikacji blokada: brak dalszych kliknięć", len(s.ataki) == 2 and not r3 and not r4, f"ataki={len(s.ataki)}")
s.t += 30
c2 = dict(c); c2["x"] = s.poz[0] + 1
b.ponow_atak(c2, poz); b.ponow_atak(c2, poz)
sprawdz("26f3 cel obok (odl <= 1): nigdy ponowienia", len(s.ataki) == 2, f"ataki={len(s.ataki)}")
sprawdz("26g loot: uciekający 10 pól stąd blokuje loot, zdrowy nie",
        b.zywy_w_poblizu([szczur(990, 110, hp=10)], (100, 100, 7)) is not None
        and b.zywy_w_poblizu([szczur(991, 110, hp=100)], (100, 100, 7)) is None)


# 26h. dwóch świeżych szczurów obok, uciekający 10% w odl 4 (HP gracza stabilne): bijemy świeżych
s = Swiat(); s.stwory = [szczur(995, 106, hp=10)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(996, s.poz[0] + 1, hp=100)); s.stwory.append(szczur(997, s.poz[0], y=101, hp=100))
n_log = len(cavelog); b.ruch_czas = s.t; b.ruch_poz = tuple(s.poz); b.tick()
sprawdz("26h >=2 świeżych obok, uciekający dalej niż 3 pola: zmiana celu na świeżego",
        any("Zmiana celu" in l for l in cavelog[n_log:]), f"cel={b.cel}")

# 26i. pętla zmiana celu / wybór rannego: po Zmianie celu bijemy świeżego do skutku (nie flap co obieg),
#      po jego zabiciu natychmiast wracamy do uciekającego (log "wracam do dobicia")
s = Swiat(); s.stwory = [szczur(1001, 104, hp=25)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(1002, s.poz[0] + 1, hp=100))
b.ruch_czas = s.t - cavebot.BLOKADA_STOI - 1; b.ruch_poz = tuple(s.poz)
b.pogon_postep = s.t - cavebot.BLOKADA_STOI - 1; b.obok_od = {1002: s.t - cavebot.BLOKADA_STOI - 1}
n_log = len(cavelog)
cele = []
for _ in range(4):
    b.tick(); cele.append(b.cel and b.cel["id"])
zm = sum(1 for l in cavelog[n_log:] if "Zmiana celu" in l)
sprawdz("26i jedna Zmiana celu, potem cel = świeży (bez flapu)", zm == 1 and cele == [1002] * 4, f"zm={zm} cele={cele}")
s.stwory = [x for x in s.stwory if x["id"] != 1002]      # świeży zabity
n_log = len(cavelog); b.tick(); b.tick()    # 1. tick: zgon celu, 2.: wybór
sprawdz("26i' po rozprawie wracamy do rannego i jest log", b.cel and b.cel["id"] == 1001
        and any("wracam do dobicia" in l for l in cavelog[n_log:]), f"cel={b.cel}")
# 26k. świeży nie ginie w ROZPRAWA_MAX: po tym czasie wracamy do rannego (w widoku, zasięg 10), log, i nie ma pętli
s = Swiat(); s.stwory = [szczur(1005, 104, hp=25)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(1006, s.poz[0] + 1, hp=100))
b.ruch_czas = s.t - cavebot.BLOKADA_STOI - 1; b.ruch_poz = tuple(s.poz)
b.pogon_postep = s.t - cavebot.BLOKADA_STOI - 1; b.obok_od = {1006: s.t - cavebot.BLOKADA_STOI - 1}
b.tick()
c1 = b.cel and b.cel["id"]; roz = b.rozprawa
sprawdz("26k rozprawa ustawiona: cel świeży, wroc = ranny", c1 == 1006 and roz and roz["wroc"] == 1005, f"cel={c1} roz={roz}")
s.t += cavebot.ROZPRAWA_MAX + 1
n_log = len(cavelog); b.tick(); b.tick()
sprawdz("26k' po ROZPRAWA_MAX świeży żyje: wracamy do rannego (log wracam do dobicia)",
        b.cel and b.cel["id"] == 1005 and any("wracam do dobicia" in l for l in cavelog[n_log:]), f"cel={b.cel}")
zm = sum(1 for l in cavelog[n_log:] if "Zmiana celu" in l)
b.tick()
sprawdz("26k'' po powrocie brak natychmiastowej pętli Zmiany celu", b.cel and b.cel["id"] == 1005
        and sum(1 for l in cavelog[n_log:] if "Zmiana celu" in l) == zm, f"cel={b.cel}")
# 26l. ranny poza zasięgiem 10 / poza widokiem: nie wracamy
s = Swiat(); s.stwory = [szczur(1007, 104, hp=25)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(1008, s.poz[0] + 1, hp=100))
b.ruch_czas = s.t - cavebot.BLOKADA_STOI - 1; b.ruch_poz = tuple(s.poz)
b.pogon_postep = s.t - cavebot.BLOKADA_STOI - 1; b.obok_od = {1008: s.t - cavebot.BLOKADA_STOI - 1}
b.tick()
s.stwory[0]["x"] = s.poz[0] + 12
s.t += cavebot.ROZPRAWA_MAX + 1
n_log = len(cavelog); b.tick()
sprawdz("26l ranny dalej niż 10: dalej bijemy świeżego", b.cel and b.cel["id"] == 1008
        and not any("wracam do dobicia" in l for l in cavelog[n_log:]), f"cel={b.cel}")

# 26j. szum odczytu HP (<3 pp) nie jest "gryzie"; spadek >= 3 pp w 2 s tak
s = Swiat(); s.stwory = [szczur(1003, 104, hp=25)]
b = zrob(s, trasa()); s.zabija = False
b.tick(); s.stwory.append(szczur(1004, s.poz[0] + 1, hp=100))
mh = s.maxhp if hasattr(s, "maxhp") else None
hp0 = s.hp; s.hp = hp0 - 1
n_log = len(cavelog); b.tick()
sprawdz("26j spadek HP o 1 pp: nie Zmiana celu", not any("Zmiana celu" in l for l in cavelog[n_log:]) and b.cel and b.cel["id"] == 1003,
        f"hp {hp0}->{s.hp} cel={b.cel}")

# 26m. korytarz 1 pole szeroki (pełna mapa): ranny 25% za dwoma świeżymi. Bot celuje w pierwszego blokującego
#      NATYCHMIAST (bez czekania BLOKADA_STOI), zabija, bierze drugiego, wraca do rannego
KOR1 = [(x, 100) for x in range(95, 116)]
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(1101, 102, hp=100), szczur(1102, 103, hp=100), szczur(1103, 106, hp=25)]
b = zrob_mapa(s, KOR1); s.zabija = False
n_log = len(cavelog); b.tick()
sprawdz("26m ranny za dwoma szczurami w korytarzu: cel = pierwszy blokujący od razu + log",
        b.cel and b.cel["id"] == 1101 and any("zablokowana przez" in l and "bije blokującego" in l for l in cavelog[n_log:]),
        f"cel={b.cel} log={cavelog[n_log:]}")
sprawdz("26m-b rozprawa: wroc = ranny, limit ~15 s", b.rozprawa and b.rozprawa["wroc"] == 1103
        and b.rozprawa["do"] - s.t > cavebot.ROZPRAWA_MAX, f"{b.rozprawa}")
s.stwory = [m for m in s.stwory if m["id"] != 1101]      # pierwszy zabity
b.tick(); b.tick()
sprawdz("26m-c po zabiciu pierwszego: celem jest drugi blokujący (nie ranny)", b.cel and b.cel["id"] == 1102, f"cel={b.cel}")
s.stwory = [m for m in s.stwory if m["id"] != 1102]      # drugi zabity
n_log = len(cavelog); b.tick(); b.tick()
sprawdz("26m-d po zabiciu obu: powrót do rannego (wracam do dobicia)", b.cel and b.cel["id"] == 1103
        and any("wracam do dobicia" in l for l in cavelog[n_log:]), f"cel={b.cel}")
# blokujący w odl 3 (nie styczny)
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(1104, 103, hp=100), szczur(1105, 107, hp=15)]
b = zrob_mapa(s, KOR1); s.zabija = False
b.tick()
sprawdz("26n blokujący w odl 3 (korytarz): celem on, nie ranny", b.cel and b.cel["id"] == 1104, f"cel={b.cel}")
# otwarte pole: ranny za szczurem, obok wolne pola: bez zmian, ranny dalej celem
SZEROKA = [(x, y) for x in range(95, 116) for y in range(97, 104)]
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(1106, 102, hp=100), szczur(1107, 105, hp=15)]
b = zrob_mapa(s, SZEROKA); s.zabija = False
n_log = len(cavelog); b.tick()
sprawdz("26o otwarte pole: bez blokady zachowanie bez zmian (ranny celem, brak logu blokady)",
        b.cel and b.cel["id"] == 1107 and not any("zablokowana przez" in l for l in cavelog[n_log:]), f"cel={b.cel}")
# 26p. B: ranny (<= 30%) w odl 2 za blokującym: bez bicia blokującego (ROZPRAWA_BLOK_MIN_HP_CELU); 0 = jak dawniej
def _blok2(minhp, hp_celu):
    global cavebot_ROZ
    stare = cavebot.ROZPRAWA_BLOK_MIN_HP_CELU; cavebot.ROZPRAWA_BLOK_MIN_HP_CELU = minhp
    try:
        s = Swiat(poz=(100,100,7)); s.stwory = [szczur(1201, 101, hp=100), szczur(1202, 102, hp=hp_celu)]
        b = zrob_mapa(s, KOR1); s.zabija = False
        n_log = len(cavelog); b.tick()
        return any("zablokowana przez" in l for l in cavelog[n_log:])
    finally:
        cavebot.ROZPRAWA_BLOK_MIN_HP_CELU = stare
sprawdz("26p-a ranny 25% w odl 2: nie bijemy blokującego", not _blok2(30, 25))
sprawdz("26p-b pokrętło 0 = dawne zachowanie (bije blokującego)", _blok2(0, 25))
sprawdz("26p-c ranny 60% w odl 2: bije blokującego jak dawniej", _blok2(30, 60))
# ranny bez blokady w korytarzu (nikt między nami): bez zmian
s = Swiat(poz=(100,100,7)); s.stwory = [szczur(1108, 106, hp=15), szczur(1109, 95, hp=100)]
b = zrob_mapa(s, KOR1); s.zabija = False
b.tick()
sprawdz("26o-b korytarz bez moba między nami a rannym: ranny celem", b.cel and b.cel["id"] == 1108, f"cel={b.cel}")

# 27. szybka pętla pościgu (poscig_szybki): czeka na ZMIANĘ pozycji, wyjścia, brak telemetrii w pętli, flaga ataku ze "stwor"
import random as _random
_random.seed(11)
def swiat_poscigu(cel_x=106, cel_hp=10, opoznienie=0.25, sciana=False, gracz_hp=100, koszt=None, rpc_poscig=True, **kw):
    s = Swiat(hp=gracz_hp); m = szczur(1100, cel_x, hp=cel_hp); m["adres"] = "0x1000"
    s.stwory = [m]; s.zabija = False
    s.atakowany = True; s.n_stwor = 0; s.n_cel_ataku = 0; s.czasy_klawiszy = []; s.oczekuje = None
    s.opoznienie = opoznienie; s.sciana = sciana; s.tele_wywolania = []; s.pozycje_czasy = []
    s.zmiany_prawdziwe = []; s.n_poscig = 0; s.rpc_czas = {}
    koszt = koszt or {}
    zap0 = s.zapytaj
    def stwor_odp():
        mm = s.stwory[0]
        if mm.get("zniknal"): return None
        return {"id": mm["id"], "x": mm["x"], "y": mm["y"], "z": mm["z"], "hp": mm["hp"],
                "atakowany": s.atakowany, "bije_nas": False}
    def zap(z):
        s.t += koszt.get(z["cmd"], 0.01 if z["cmd"] in ("stwor", "poscig") else 0.0)
        s.rpc_czas[z["cmd"]] = s.rpc_czas.get(z["cmd"], 0) + 1
        if z["cmd"] == "poscig":
            if not rpc_poscig: raise RuntimeError("nieznane polecenie: poscig")
            s.n_poscig += 1
            x, y, zz = b.postac.pozycja()
            return {"pozycja": {"x": x, "y": y, "z": zz}, "stwor": stwor_odp()}
        if z["cmd"] == "stwor":
            s.n_stwor += 1
            return {"stwor": stwor_odp()}
        if z["cmd"] == "cel_ataku":
            s.n_cel_ataku += 1
        return zap0(z)
    s.zapytaj = zap
    b = zrob_klik(s, trasa(), **kw)
    def klawisz(k):
        s.klawisze.append(k); s.czasy_klawiszy.append(s.t)
        if k in bot.KIERUNKI and not s.sciana:
            d = bot.KIERUNKI[k]; s.oczekuje = (s.t + s.opoznienie, s.poz[0] + d[0], s.poz[1] + d[1])
    def pozycja():
        s.t += koszt.get("pozycja", 0.0)
        if s.oczekuje and s.t >= s.oczekuje[0]:
            s.zmiany_prawdziwe.append(s.oczekuje[0])
            s.poz[0], s.poz[1] = s.oczekuje[1], s.oczekuje[2]; s.oczekuje = None; s.pozycje_czasy.append(s.t)
        return tuple(s.poz)
    b.postac.klawisz = klawisz; b.postac.pozycja = pozycja
    class Tele:
        def zdarzenie(self, typ, **d): s.tele_wywolania.append((typ, d, b.w_poscigu))
        def probka(self, *a): s.tele_wywolania.append(("probka", {}, b.w_poscigu)); return None
        def linia(self, *a): pass
    class Pokr:
        def odswiez(self): s.tele_wywolania.append(("pokretla", {}, b.w_poscigu))
    b.tele = Tele(); b.pokretla = Pokr(); b.pokretla_ost = float("-inf")
    b.czy_atakowany = b._atakowany_domyslny   # odczyt z pola "atakowany" jak na żywo, bez zrzutu ekranu
    return s, b
def start_poscig(s, b):
    c = dict(s.stwory[0]); poz = tuple(s.poz)
    g = {"hp": s.hp, "max_hp": s.max_hp, "proc": 100.0 * s.hp / s.max_hp}
    return b.poscig_szybki(c, poz, g)
def zdarzenia(s, typ): return [d for t, d, w in s.tele_wywolania if t == typ]

# 27a. pętla czeka na zmianę pozycji: odstępy między strzałkami >= czas kroku, brak telemetrii w pętli, dojście do celu
s, b = swiat_poscigu()
t0 = s.t; r = start_poscig(s, b)
odstepy = [b2 - a for a, b2 in zip(s.czasy_klawiszy, s.czasy_klawiszy[1:])]
sprawdz("27a pętla dochodzi obok celu (odl<=1) strzałkami w prawo",
        r is True and s.poz[0] == 105 and s.klawisze and set(s.klawisze) == {"Right"}, f"poz={s.poz} klaw={s.klawisze}")
sprawdz("27a2 strzałka dopiero po zmianie pozycji: odstępy >= czasu kroku (0,25 s), tyle strzałek co zmian pozycji",
        len(odstepy) >= 3 and min(odstepy) >= 0.25 - 1e-6 and len(s.czasy_klawiszy) == len(s.pozycje_czasy),
        f"odstepy={odstepy} klawisze={len(s.czasy_klawiszy)} zmiany={len(s.pozycje_czasy)}")
sprawdz("27a3 brak telemetrii/próbek/pokręteł w pętli; tylko start i koniec poza pętlą",
        [t for t, d, w in s.tele_wywolania if w] == [] and [t for t, d, w in s.tele_wywolania if t != "decyzja"] == ["poscig_start", "poscig_koniec"],   # 15.10: decyzja D2 jest przed pętlą
        s.tele_wywolania)
koniec = zdarzenia(s, "poscig_koniec")[0]
sprawdz("27a4 poscig_koniec: kroki, czas, powód",
        koniec["powod"] == "odl<=1" and koniec["kroki"] == 5 and koniec["czas"] > 0 and not b.w_poscigu, koniec)
dd2 = zdarzenia(s, "decyzja"); start = zdarzenia(s, "poscig_start")[0]
sprawdz("27a5 decyzja D2 (15.10): jeden rekord, id w poscig_start i poscig_koniec, cel i opcja gonić",
        len(dd2) == 1 and dd2[0]["rodzaj"] == "D2" and dd2[0]["wybrana"] == "gonic" and dd2[0]["cel_id"] == 1100
        and start.get("decyzja_id") == dd2[0]["id"] == koniec.get("decyzja_id") and dd2[0]["opcje"][0]["odl"] == 6,
        (dd2, start.get("decyzja_id"), koniec.get("decyzja_id")))

# 27b. brak zmiany pozycji > POSCIG_BRAK_ZMIANY (ściana/blokada): jedna strzałka, wyjście po ~0,45 s
s, b = swiat_poscigu(sciana=True)
t0 = s.t; r = start_poscig(s, b)
koniec = zdarzenia(s, "poscig_koniec")[0]
sprawdz("27b ściana: strzałka + jedno ponowienie, wyjście bez długiego czekania, powód brak_ruchu",
        r is True and len(s.klawisze) == 1 + cavebot.POSCIG_PONOW_BRAK and koniec["ponow_brak"] == cavebot.POSCIG_PONOW_BRAK and koniec["powod"] == "brak_ruchu" and s.t - t0 < 0.45 * (1 + cavebot.POSCIG_PONOW_BRAK) + 0.4 and not b.w_poscigu,
        f"klaw={s.klawisze} dt={s.t - t0:.2f} {koniec}")

# 27c. wyjścia: cel martwy / zniknął, HP gracza spadło, gryzący potwór obok, obcy gracz, okno
s, b = swiat_poscigu(); s.stwory[0]["hp"] = 0
start_poscig(s, b)
sprawdz("27c cel martwy: wyjście bez kroku", zdarzenia(s, "poscig_koniec")[0]["powod"] == "cel_martwy" and not s.klawisze)
s, b = swiat_poscigu(); s.stwory[0]["zniknal"] = True
start_poscig(s, b)
sprawdz("27c2 cel zniknął: wyjście bez kroku", zdarzenia(s, "poscig_koniec")[0]["powod"] == "cel_znikl" and not s.klawisze)

s, b = swiat_poscigu(opoznienie=0.3)
spij0 = b.spij
def spij_bije(d):
    spij0(d)
    if len(s.klawisze) >= 2: s.hp = 70          # po drugim kroku HP spada o 30 pp
b.spij = spij_bije
start_poscig(s, b)
sprawdz("27d HP gracza spadło >= POSCIG_HP_SPADEK: wyjście", zdarzenia(s, "poscig_koniec")[0]["powod"] == "hp_spadek"
        and 2 <= len(s.klawisze) <= 6, f"{zdarzenia(s, 'poscig_koniec')} klaw={len(s.klawisze)}")

s, b = swiat_poscigu(opoznienie=0.3, cel_hp=60)   # ranny <= POSCIG_GRYZACY_MIN_HP nie jest porzucany (27e2)
spij1 = b.spij
def spij_gryzie(d):
    spij1(d)
    if len(s.klawisze) >= 2 and len(s.stwory) == 1:
        s.stwory.append(szczur(1101, s.poz[0] + 1, hp=100))   # świeży potwór obok
    if len(s.stwory) == 2:
        s.stwory[1]["x"] = s.poz[0] + 1                       # gryzie dalej (przegląd co POSCIG_PRZEGLAD s)
b.spij = spij_gryzie
start_poscig(s, b)
sprawdz("27e nowy potwór obok: wyjście (gryzący)", zdarzenia(s, "poscig_koniec")[0]["powod"] == "gryzacy",
        zdarzenia(s, "poscig_koniec"))

# 27e2. A: ranny cel (<= POSCIG_GRYZACY_MIN_HP) w odl <= 3: gryzący nie przerywa pościgu; 0 = wyłączone
def _gryzacy(minhp, cel_x, cel_hp=10):
    stare = cavebot.POSCIG_GRYZACY_MIN_HP; cavebot.POSCIG_GRYZACY_MIN_HP = minhp
    try:
        s, b = swiat_poscigu(opoznienie=0.3, cel_x=cel_x, cel_hp=cel_hp)
        sp = b.spij
        def spij_g(d):
            sp(d)
            if len(s.klawisze) >= 3 and len(s.stwory) == 1:
                s.stwory.append(szczur(1101, s.poz[0] + 1, hp=100))
            if len(s.stwory) == 2:
                s.stwory[1]["x"] = s.poz[0] + 1
        b.spij = spij_g
        start_poscig(s, b)
        return [d["powod"] for d in zdarzenia(s, "poscig_koniec")]
    finally:
        cavebot.POSCIG_GRYZACY_MIN_HP = stare
sprawdz("27e2-a ranny 10% w odl <= 3: gryzący nie przerywa", "gryzacy" not in _gryzacy(30, 107), _gryzacy(30, 107))
sprawdz("27e2-b pokrętło 0: gryzący przerywa jak dawniej", "gryzacy" in _gryzacy(0, 107), _gryzacy(0, 107))
sprawdz("27e2-c ranny 80% (> progu): gryzący przerywa", "gryzacy" in _gryzacy(30, 107, 80), _gryzacy(30, 107, 80))
sprawdz("27e2-d ranny w odl > 3: gryzący przerywa", "gryzacy" in _gryzacy(30, 112), _gryzacy(30, 112))
import pokretla as _pkc
sprawdz("27e2-e pokrętła w ZAKRESY", all(k in _pkc.ZAKRESY for k in ("POSCIG_GRYZACY_MIN_HP", "ROZPRAWA_BLOK_MIN_HP_CELU", "PATROL_POWROT_DO_CELU", "PATROL_POWROT_MAX_ODL")))

s, b = swiat_poscigu(opoznienie=0.3)
spij2 = b.spij
def spij_gracz(d):
    spij2(d)
    if len(s.klawisze) >= 1 and len(s.stwory) == 1:
        s.stwory.append(gracz_obcy("GM Tester", id=77, x=s.poz[0] + 3))
b.spij = spij_gracz
start_poscig(s, b)
sprawdz("27f groźny gracz (GM): wyjście", zdarzenia(s, "poscig_koniec")[0]["powod"] == "obcy_gracz",
        zdarzenia(s, "poscig_koniec"))

s, b = swiat_poscigu(opoznienie=0.3)
spij3 = b.spij
def spij_zwykly(d):
    spij3(d)
    if len(s.klawisze) >= 1 and len(s.stwory) == 1:
        s.stwory.append(gracz_obcy("Obcy", id=78, x=s.poz[0] + 3))
b.spij = spij_zwykly
start_poscig(s, b)
sprawdz("27f2 zwykły gracz: pętla NIE przerywa się", zdarzenia(s, "poscig_koniec")[0]["powod"] != "obcy_gracz",
        zdarzenia(s, "poscig_koniec"))

# wejście: zwykły gracz nie blokuje, GM/PK blokuje
s, b = swiat_poscigu()
poz = tuple(s.poz); cel = s.stwory[0]
b.ostatnie_stwory = [cel, gracz_obcy("Obcy", id=79, x=poz[0] + 2)]
sprawdz("27f3 wejście: zwykły gracz nie blokuje", b.poscig_wejscie(cel, {"proc": 100.0}, poz, 5) is True)
b.ostatnie_stwory = [cel, gracz_obcy("GM Tester", id=79, x=poz[0] + 2)]
sprawdz("27f4 wejście: GM blokuje", b.poscig_wejscie(cel, {"proc": 100.0}, poz, 5) is False)
b.ostatnie_stwory = [cel, gracz_obcy("Obcy", id=79, x=poz[0] + 2, czaszka=1)]
sprawdz("27f5 wejście: czaszka/PK blokuje", b.poscig_wejscie(cel, {"proc": 100.0}, poz, 5) is False)

s, b = swiat_poscigu(cel_x=140, opoznienie=0.2)
start_poscig(s, b)
k = zdarzenia(s, "poscig_koniec")[0]
sprawdz("27g okno POSCIG_OKNO (3 s): wyjście po czasie",
        k["powod"] == "okno" and 2.9 <= k["czas"] <= cavebot.POSCIG_OKNO_DOBRY + 0.8 and k["kroki"] >= 6, k)

# 27g2. okno: dobry postęp przedłuża do POSCIG_OKNO_DOBRY, brak postępu (odl nie maleje) kończy po POSCIG_OKNO
sprawdz("27g2 dobry postęp: okno przedłużone ponad POSCIG_OKNO", k["czas"] > cavebot.POSCIG_OKNO, k)

# 27n. jedno RPC "poscig": brak osobnych "stwor"/"pozycja" w obrocie; starszy rdzeń = dwa zapytania jak dawniej
s, b = swiat_poscigu(cel_x=140, opoznienie=0.3)
start_poscig(s, b)
sprawdz("27n RPC poscig: zero zapytań stwor, wiele poscig", s.n_stwor == 0 and s.n_poscig >= 10, f"stwor={s.n_stwor} poscig={s.n_poscig}")
s, b = swiat_poscigu(cel_x=140, opoznienie=0.3, rpc_poscig=False)
start_poscig(s, b)
k2 = zdarzenia(s, "poscig_koniec")[0]
sprawdz("27n2 rdzeń bez komendy poscig: działa na stwor + pozycja, bez ponawiania komendy",
        s.n_poscig == 0 and s.n_stwor >= 10 and k2["kroki"] >= 6 and b._poscig_rpc is False, f"{s.n_stwor} {k2}")

# 27o. czas decyzja -> klawisz i kroki/s: nowa pętla vs poprzednia (kopia starej pętli w atrapie), RPC jak na żywo
def poscig_stary(b, cel, poz):
    """Poprzednia pętla (przed przyspieszeniem): osobne RPC stwor + pozycja, przegląd co 0,5 s przed strzałką,
    poll 0,05-0,08, opóźnienie po kroku 0,03-0,12."""
    s_ = None; t0 = b.zegar(); koniec = t0 + 3.0; poz = tuple(poz); przeglad = t0; ost = float("-inf")
    kroki = 0; hp_ref = 100.0; dec = []; t_wykr = None
    while b.zegar() < koniec:
        s_ = b.zapytaj({"cmd": "stwor", "adres": cel["adres"], "id": cel["id"]})["stwor"]
        if s_ is None or b.dystans((s_["x"], s_["y"]), poz) <= 1: break
        cel = {**cel, "x": s_["x"], "y": s_["y"]}
        if b.zegar() - przeglad >= 0.5:
            przeglad = b.zegar(); b.gracz(); b.stwory()
        b.ponow_atak(cel, poz)
        reszta = 0.09 - (b.zegar() - ost)
        if reszta > 0: b.spij(reszta)
        b.podejdz((s_["x"], s_["y"]), poz, pilne=True, natychmiast=True, poscig=True)
        if t_wykr is not None: dec.append(b.zegar() - t_wykr); t_wykr = None
        ost = b.zegar()
        nowa = None
        while True:
            b.spij(_random.uniform(0.05, 0.08))
            p = tuple(b.postac.pozycja())
            if p != poz: nowa = p; break
            if b.zegar() - ost > 0.45: break
        if nowa is None: break
        kroki += 1; t_wykr = b.zegar(); poz = nowa
        b.pauza(0.25, 0.45) if _random.random() < 0.125 else b.pauza(0.03, 0.12)
    return kroki, b.zegar() - t0, dec
KOSZT = {"stwor": 0.035, "poscig": 0.04, "pozycja": 0.035, "gracz": 0.035, "stwory": 0.25}
def mediana(l): l = sorted(l); return l[len(l) // 2] if l else None
dec_s, dec_n, ks_s, ks_n = [], [], [], []
for i in range(6):
    _random.seed(100 + i)
    s, b = swiat_poscigu(cel_x=140, opoznienie=0.45, koszt=KOSZT)
    b.spij = lambda d, s=s: setattr(s, "t", s.t + d)
    poz0 = tuple(s.poz)
    kr, cz, dec = poscig_stary(b, dict(s.stwory[0]), poz0)
    dec_s += dec; ks_s.append(kr / cz)
    _random.seed(100 + i)
    s, b = swiat_poscigu(cel_x=140, opoznienie=0.45, koszt=KOSZT)
    b.spij = lambda d, s=s: setattr(s, "t", s.t + d)
    start_poscig(s, b)
    k = zdarzenia(s, "poscig_koniec")[0]
    ks_n.append(k["kroki_na_s"])
    # decyzja: od wykrycia zmiany pozycji do klawisza (czasy z atrapy)
    dec_n += [kl - pz for pz, kl in zip(s.pozycje_czasy, s.czasy_klawiszy[1:])]
d_s, d_n = sum(dec_s) / len(dec_s), sum(dec_n) / len(dec_n)
print(f"     pomiar: decyzja->klawisz przed {d_s:.3f} s, po {d_n:.3f} s; kroki/s przed {sum(ks_s)/len(ks_s):.2f}, po {sum(ks_n)/len(ks_n):.2f}")
sprawdz("27o czas decyzja -> klawisz: <= 50% poprzedniego", d_n <= 0.5 * d_s, f"{d_n:.3f} vs {d_s:.3f}")
sprawdz("27o2 kroki/s: >= +10% przy tym samym kroku gry (0,45 s)", sum(ks_n) >= 1.1 * sum(ks_s), f"{sum(ks_n)/6:.2f} vs {sum(ks_s)/6:.2f}")
odstepy = [b2 - a for a, b2 in zip(s.czasy_klawiszy, s.czasy_klawiszy[1:])]
sprawdz("27o3 odstęp między strzałkami >= POSCIG_KROK_MIN", all(o >= cavebot.POSCIG_KROK_MIN - 1e-9 for o in odstepy), min(odstepy))

# 27p. wolne pole (prędkość 20 ~0,9 s/krok): próg braku zmiany rośnie, krok trwający 1,0 s nie jest "ścianą"
s, b = swiat_poscigu(cel_x=140, opoznienie=1.0)
b._czas_kroku = lambda poz: 20 * cavebot.POSCIG_KROK_S_NA_PREDKOSC
start_poscig(s, b)
k = zdarzenia(s, "poscig_koniec")[0]
sprawdz("27p wolne pole: kroki trwające 1,0 s nie kończą pętli brak_ruchu", k["powod"] != "brak_ruchu" and k["kroki"] >= 3 and k["ponow_brak"] == 0, k)
s, b = swiat_poscigu(cel_x=140, opoznienie=1.0)
start_poscig(s, b)
sprawdz("27p2 bez wiedzy o polu (0.45 s): ten sam krok = ponowienie i brak_ruchu (próg stały)",
        zdarzenia(s, "poscig_koniec")[0]["powod"] == "brak_ruchu")
b2 = zrob_klik(Swiat(), trasa())
b2.mapa = types.SimpleNamespace(pole=lambda x, y, z: (1, 0, 12 if (x, y) != (101, 100) else 20), flagi=lambda *a: 0)
sprawdz("27p3 _czas_kroku: najwolniejsze z pola i sąsiadów", abs(b2._czas_kroku((100, 100, 7)) - 20 * cavebot.POSCIG_KROK_S_NA_PREDKOSC) < 1e-9)
b2.mapa = None
sprawdz("27p4 _czas_kroku bez mapy = 0", b2._czas_kroku((100, 100, 7)) == 0.0)
# 27q. ciągła pętla: okno przedłużane po świeżym przeglądzie (bez powrotu do ticka), do POSCIG_OKNO_DOBRY
s, b = swiat_poscigu(cel_x=160, opoznienie=0.4)
start_poscig(s, b)
k = zdarzenia(s, "poscig_koniec")[0]
sprawdz("27q ciągły pościg: jedna pętla dłużej niż POSCIG_OKNO, do POSCIG_OKNO_DOBRY",
        k["czas"] > cavebot.POSCIG_OKNO + 1.0 and k["czas"] <= cavebot.POSCIG_OKNO_DOBRY + 0.6 and k["powod"] == "okno", k)
sprawdz("27q2 zawahanie rzadziej niż 1 na 10", cavebot.POSCIG_ZAWAHANIE_P <= 0.1)

# 27h. hook mózgu (wstrzymanie / rozmowa) przerywa pętlę
s, b = swiat_poscigu()
b._poscig_przerwanie = lambda: "wstrzymanie"
start_poscig(s, b)
sprawdz("27h pauza mózgu: wyjście przed pierwszym krokiem", zdarzenia(s, "poscig_koniec")[0]["powod"] == "wstrzymanie" and not s.klawisze)

# 27i. ponow_atak w pętli: flaga ze "stwor", bez cel_ataku; klik tylko po 2 odczytach False, weryfikacja w następnym obrocie
s, b = swiat_poscigu(cel_x=107, opoznienie=0.3); s.atakowany = False
b.atak_czas = float("-inf")
start_poscig(s, b)
sprawdz("27i flaga ataku False z \"stwor\": klik ponawiający (+ cofający po weryfikacji), nigdy cel_ataku",
        s.n_cel_ataku == 0 and 1 <= len(s.ataki) <= 2, f"cel_ataku={s.n_cel_ataku} ataki={len(s.ataki)}")
s, b = swiat_poscigu(cel_x=107, opoznienie=0.3); s.atakowany = True
start_poscig(s, b)
sprawdz("27i2 atak trwa (flaga True): żadnego kliku, żadnego cel_ataku", s.n_cel_ataku == 0 and not s.ataki,
        f"cel_ataku={s.n_cel_ataku} ataki={len(s.ataki)}")
s, b = swiat_poscigu(); s.atakowany = False
b.atak_czas = float("-inf")
zap_przed = s.zapytaj
wolane = []
s.zapytaj = lambda z: (wolane.append(z["cmd"]), zap_przed(z))[1]; b.zapytaj = s.zapytaj
c = {**s.stwory[0], "atakowany": False}
b.ponow_atak(c, tuple(s.poz)); b.ponow_atak(c, tuple(s.poz))
sprawdz("27j ponow_atak z polem atakowany: zero zapytań do rdzenia (bez cel_ataku/stwory), klik po 2 odczytach",
        wolane == [] and len(s.ataki) == 1, f"wolane={wolane} ataki={len(s.ataki)}")

# 27k. wejście w pętlę z walcz(): zdrowy cel oddalający się też; wyjątki wejścia
def tick_poscig(s, b):
    b.tick()
    return zdarzenia(s, "poscig_start")
s, b = swiat_poscigu(cel_x=106, cel_hp=100)
n = tick_poscig(s, b)
sprawdz("27k zdrowy cel (hp 100%) w odl 6: szybka pętla (nie tylko uciekający)", len(n) == 1, s.tele_wywolania)
s, b = swiat_poscigu(cel_x=106, cel_hp=100); s.stwory.append(szczur(1102, 101, hp=100))
n = tick_poscig(s, b)
sprawdz("27k2 inny potwór obok: bez szybkiej pętli", len(n) == 0, s.tele_wywolania)
s, b = swiat_poscigu(cel_x=106, cel_hp=100, gracz_hp=48)
n = tick_poscig(s, b)
sprawdz("27k3 HP gracza <= próg + margines: bez szybkiej pętli", len(n) == 0, s.tele_wywolania)
s, b = swiat_poscigu(cel_x=106, cel_hp=100); s.stwory.append(gracz_obcy("GM Tester", id=78, x=103, y=103))
n = tick_poscig(s, b)
sprawdz("27k4 groźny gracz (GM) w zasięgu: bez szybkiej pętli", len(n) == 0, s.tele_wywolania)
# ZMIANA CELOWA (unikanie.py): cel 3 pola od zwykłego gracza nie jest celem (nie kradniemy), więc gracz stoi dalej od celu
s, b = swiat_poscigu(cel_x=106, cel_hp=100); s.stwory.append(gracz_obcy("Obcy", id=78, x=99, y=104))
n = tick_poscig(s, b)
sprawdz("27k4b zwykły gracz w zasięgu: szybka pętla wchodzi", len(n) > 0, s.tele_wywolania)
s, b = swiat_poscigu(cel_x=106, cel_hp=100)
b.w_lootcie = True
n = tick_poscig(s, b)
sprawdz("27k5 trwa loot: bez szybkiej pętli", len(n) == 0, s.tele_wywolania)
s, b = swiat_poscigu(cel_x=101, cel_hp=100)
n = tick_poscig(s, b)
sprawdz("27l cel obok (odl 1): bez szybkiej pętli", len(n) == 0, s.tele_wywolania)

# 27m. ciągły pościg bez zbliżania się > POSCIG_SERIA_MAX: krótka przerwa od szybkiej pętli
s, b = swiat_poscigu()
b.poscig_seria = [s.t - cavebot.POSCIG_SERIA_MAX - 1, 4, s.t - 0.2]
c = dict(s.stwory[0]); poz = tuple(s.poz)
w1 = b.poscig_wejscie(c, {"proc": 100.0}, poz, 5)
w2 = b.poscig_wejscie(c, {"proc": 100.0}, poz, 5)
s.t += cavebot.POSCIG_PRZERWA + 0.1
w3 = b.poscig_wejscie(c, {"proc": 100.0}, poz, 5)
sprawdz("27m po SERIA_MAX bez zbliżania: przerwa POSCIG_PRZERWA, potem znów wolno", w1 is False and w2 is False and w3 is True,
        f"{w1} {w2} {w3}")

# 28. ucieczka przy niskim HP (prog 30%): odczyty co kilka sekund, spadek 100 -> 31 -> 29 w kolejnych tickach
def swiat_ucieczki(rat_x=102, **kw):
    s = Swiat(poz=(105, 100, 7), hp=100); s.stwory = [szczur(2800, rat_x, hp=100)]; s.zabija = False
    b = zrob(s, trasa(), prog_hp=30, okrazenia=99, **kw); b.idx = 6
    return s, b
s, b = swiat_ucieczki(rat_x=106)
b.tick(); sprawdz("28a przed spadkiem HP: walka", b.stan == "WALKA" and not b.ucieczka, b.stan)
s.hp = 31; s.t += 3; n_ataki = len(s.ataki); b.tick()
sprawdz("28b HP 100 -> 31 (nad progiem 30, ale spadek o 69 pp): od razu UCIECZKA, bez ataku",
        b.ucieczka and b.stan == "UCIECZKA" and len(s.ataki) == n_ataki, f"stan={b.stan} uc={b.ucieczka}")
s.hp = 29; b.tick(); sprawdz("28c HP 29%: nadal UCIECZKA, cel zdjęty", b.ucieczka and b.cel is None)
# spadek w małych krokach: 45 -> 38 -> 33 (kolejne uderzenie 7 pp zrzuciłoby pod 30) = wejście przy 33
s, b = swiat_ucieczki(rat_x=106); s.hp = 45
b.tick(); s.hp = 38; s.t += 0.7; b.tick(); sprawdz("28d HP 38 po spadku o 7: jeszcze walka", not b.ucieczka, b.stan)
s.hp = 33; s.t += 0.7; b.tick()
sprawdz("28e HP 33 po spadku o 5 (kolejne uderzenie zrzuci pod 30): predykcja = UCIECZKA", b.ucieczka)
# bez spadku HP próg działa jak dotąd: 31% bez ugryzienia to jeszcze nie ucieczka, 30% już tak
s, b = swiat_ucieczki(rat_x=106); s.hp = 31; b.tick(); b.tick()
sprawdz("28f stałe 31% (bez spadku): bez ucieczki", not b.ucieczka)
s.hp = 30; b.tick(); sprawdz("28g 30% = próg: UCIECZKA (<=)", b.ucieczka)
# w trakcie pościgu (szybka pętla): HP spada, kolejny tick = UCIECZKA, bez nowego pościgu i ataku
s, b = swiat_poscigu(cel_x=106, cel_hp=100, prog_hp=30)
tick_poscig(s, b)
n_start = len(zdarzenia(s, "poscig_start")); n_ataki = len(s.ataki)
s.hp = 31; s.t += 2.0; b.tick()
sprawdz("28h w pościgu: HP 100 -> 31: UCIECZKA, brak nowego pościgu i ataku",
        b.ucieczka and len(zdarzenia(s, "poscig_start")) == n_start and len(s.ataki) == n_ataki and not b.w_poscigu,
        f"stan={b.stan}")
# w trakcie lootu: zwłoki w odl 4, HP spadło: przerwanie lootu (zwłoki odłożone), bez zbierania
s = Swiat(poz=(105, 100, 7), hp=31); s.stwory = []
b = zrob(s, trasa(), prog_hp=30); b.prog_aktualny = 30.0
b.zbierz_loot((109, 100, 7))
sprawdz("28i loot przy HP 31%: przerwany, zwłok nie zbieramy, zwłoki odłożone",
        b.lootlog == [] and (109, 100, 7) in [z for z, _ in b.zwloki_czekajace] and s.poz[0] == 105,
        f"loot={b.lootlog} czekajace={b.zwloki_czekajace} poz={s.poz}")
s = Swiat(poz=(105, 100, 7), hp=100); b = zrob(s, trasa(), prog_hp=30); b.prog_aktualny = 30.0
b.zbierz_loot((106, 100, 7)); sprawdz("28i2 loot przy HP 100%: zbiera", b.lootlog == [(106, 100, 7)])
# po tej ucieczce: bez regeneracji (brak jedzenia) bot nie stoi bez końca; z regeneracją wraca przy >= 60%
s, b = swiat_ucieczki(rat_x=130); s.hp = 25; b.tick()
sprawdz("28j start ucieczki przy 25%", b.ucieczka)
s.hp = 50; s.t += 5; b.tick()
sprawdz("28k 50% po 5 s: jeszcze w ucieczce (histereza do 60%)", b.ucieczka)
s.t += cavebot.UCIECZKA_ODPOCZYNEK_S; b.tick()
sprawdz("28l 50% bez regeneracji po odpoczynku: wraca do gry w trybie ostrożnym",
        not b.ucieczka and b.ostrozny, f"uc={b.ucieczka} ostr={b.ostrozny}")
c = dict(szczur(1, 108)); poz = tuple(s.poz)
sprawdz("28m tryb ostrożny: bez szybkiego pościgu", b.poscig_wejscie(c, {"proc": 50.0}, poz, 5) is False)
s.hp = 70; s.t += 1; b.tick()
sprawdz("28n HP >= 60%: koniec trybu ostrożnego", not b.ostrozny and not b.ucieczka)
s, b = swiat_ucieczki(rat_x=130); s.hp = 35; b.tick(); s.hp = 25; b.tick()
s.hp = 33; s.t += cavebot.UCIECZKA_ODPOCZYNEK_S + 5; b.tick()
sprawdz("28o HP 25-33% bez regeneracji: zostaje w ucieczce (za nisko na grę)", b.ucieczka and not b.ostrozny)
# jedzenie w ucieczce (bez jedzenia HP nie rośnie): klawisz jedzenia, gdy nikogo obok
s, b = swiat_ucieczki(rat_x=130, jedzenie="F2"); s.hp = 25; b.tick()
s.t += cavebot.CZAS_JEDZENIA + 1; b.tick()
sprawdz("28p w ucieczce, nikt obok, brak wzrostu HP: je (F2)", "F2" in s.klawisze, s.klawisze)
s, b = swiat_ucieczki(rat_x=106, jedzenie="F2"); s.hp = 25; b.tick()
s.t += cavebot.CZAS_JEDZENIA + 1; b.tick()
sprawdz("28q w ucieczce, szczur 1 pole: nie je", "F2" not in s.klawisze, s.klawisze)
# rozrzut progu tylko w górę (próg 30 to dolna granica)
cavebot.ROZRZUT_PROGU = 5.0
pr = []
for i in range(30):
    s, b = swiat_ucieczki(rat_x=106); b.tick(); pr.append(b.prog_aktualny)
cavebot.ROZRZUT_PROGU = 0.0
sprawdz("28r próg ucieczki w [30, 35]", min(pr) >= 30 and max(pr) <= 35 and len(set(round(x, 1) for x in pr)) > 5, f"{min(pr)}..{max(pr)}")

# 29. brak jedzenia nie przerywa gry (HP nad progiem ucieczki): bez pauz, trybu ostrożnego, alarmów i spamu
logi_cb = []
cavebot.HAKI_LOGU.append(logi_cb.append)
wyw = []
def zjedz_nic(log=print):
    wyw.append(s.t); log("jedzenie: brak jedzenia w plecaku"); return []
s = Swiat(hp=80); s.regen = False; b = zrob_klik(s, trasa(), prog_hp=30, okrazenia=99)
b.przerwa_od = float("inf")   # losowa przerwa (20-40 min) nie jest tematem tego testu
b.loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=zjedz_nic)
stany, t_start = set(), s.t
while s.t - t_start < 1500:
    b.tick(); stany.add(b.stan); s.t += 20
nic = [l for l in logi_cb if "Zjedzono: nic" in l]
brak_jedz = [l for l in logi_cb if "brak jedzenia" in l]
sprawdz("29a HP 80% bez jedzenia: nigdy UCIECZKA/PAUZA/GRACZ", not (stany & {"UCIECZKA", "PAUZA", "GRACZ", "PRZERWA"}), stany)
sprawdz("29b brak ucieczki, trybu ostrożnego i alarmów", not b.ucieczka and not b.ostrozny and s.alarmy == [],
        f"uc={b.ucieczka} ostr={b.ostrozny} alarmy={s.alarmy}")
sprawdz("29c próby jedzenia nie częściej niż co JEDZENIE_PONOW s",
        1 <= len(wyw) <= 1 + 1500 // cavebot.JEDZENIE_PONOW and all(y - x >= cavebot.JEDZENIE_PONOW - 1 for x, y in zip(wyw, wyw[1:])),
        f"próby={wyw}")
sprawdz("29d jedna linia 'brak jedzenia' w logu na godzinę (też z loot.zjedz)", len(nic) == 1 and len(brak_jedz) == 1,
        f"{len(nic)} {brak_jedz}")
# potwór w odl <= 8 (stoi, nie ginie): bez jedzenia z plecaka (dawne zachowanie; od JEDZENIE_W_WALCE=1 głód w walce wygrywa)
wyw.clear()
cavebot.JEDZENIE_W_WALCE = 0
s = Swiat(hp=80); s.stwory = [szczur(2900, 107)]; s.zabija = False
b = zrob_klik(s, trasa(), prog_hp=30, okrazenia=99); b.loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=zjedz_nic)
for _ in range(8):
    b.tick(); s.t += 40
sprawdz("29e potwór w odl <= 8: nie jemy z plecaka", wyw == [] and cavebot.JEDZENIE_SPOKOJ == 8, f"próby={wyw}")
cavebot.JEDZENIE_W_WALCE = 1
s.stwory = []
for _ in range(4):
    b.tick(); s.t += 40
sprawdz("29e' po zniknięciu potwora: próba jedzenia", len(wyw) >= 1, f"próby={wyw}")
# HP 28% (<= próg 30): ucieczka jak dotąd, ale alarm najwyżej raz na 5 min, bez pętli co 15 s
s, b = swiat_ucieczki(rat_x=130); s.hp = 28
b.loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=print: [])
b.tick()
sprawdz("29f HP 28%: ucieczka", b.ucieczka and b.stan == "UCIECZKA", b.stan)
t0 = s.t
while s.t - t0 < 290:
    s.t += 15; b.tick()
sprawdz("29g ucieczka przez ~5 min: jeden alarm", len([a for a in s.alarmy if "niskie HP" in a]) == 1, s.alarmy)
s.t += 20; b.tick()
sprawdz("29h po 5 min kolejny alarm", len([a for a in s.alarmy if "niskie HP" in a]) == 2, s.alarmy)
cavebot.HAKI_LOGU.remove(logi_cb.append) if logi_cb.append in cavebot.HAKI_LOGU else None

# 30. pościg TRZYMANYM klawiszem (POSCIG_TRZYMAJ): ciągły marsz, zmiana kierunku bez luki, puszczanie przy każdym wyjściu
KOSZT_T = dict(KOSZT, stwory=0.04)   # "stwory" z maks_wiek to odczyt cache skanera rdzenia (RPC), nie świeży skan 0,25 s
def swiat_trzymaj(cel_x=140, cel_y=100, opoznienie=0.45, blokada=False, koszt=None, **kw):
    """Atrapa klienta OTClient: krok trwa `opoznienie` s, po jego końcu rusza następny, jeśli klawisz jest trzymany
    (kierunek kroku wybierany w chwili startu; nowy klawisz w trakcie kroku czeka na kolejny)."""
    s, b = swiat_poscigu(cel_x=cel_x, opoznienie=opoznienie, koszt=koszt or KOSZT_T, **kw)
    s.stwory[0]["y"] = cel_y
    s.trzym = None; s.krok = None; s.zd = []; s.pulsy = 0; s.taps = []; s.blokada = blokada; s.zajete = set()
    def advance():
        while s.krok is not None and s.t >= s.krok[0] + s.opoznienie:
            tc, v = s.krok[0] + s.opoznienie, s.krok[1]
            nx, ny = s.poz[0] + v[0], s.poz[1] + v[1]
            if not s.blokada and (nx, ny) not in s.zajete and (nx, ny) != (s.stwory[0]["x"], s.stwory[0]["y"]):
                s.poz[0], s.poz[1] = nx, ny; s.pozycje_czasy.append(tc)
            s.krok = (tc, s.trzym) if s.trzym else None
    def trzymaj_kierunek(dx, dy):
        advance()
        s.zd.append((round(s.t, 3), "zmien" if s.trzym else "nacisnij", (dx, dy)))
        s.trzym = (dx, dy)
        if s.krok is None: s.krok = (s.t, s.trzym)
    def puszczaj():
        advance()
        if s.trzym is not None: s.zd.append((round(s.t, 3), "puść", s.trzym))
        s.trzym = None
    def pozycja():
        s.t += 0.035; advance(); return tuple(s.poz)
    p = b.postac
    p.trzymaj_kierunek = trzymaj_kierunek; p.puszczaj = puszczaj; p.pozycja = pozycja
    p.trzymany_kierunek = lambda: s.trzym
    p.puls = lambda: setattr(s, "pulsy", s.pulsy + 1)
    p.klawisz = lambda k: s.taps.append(k)
    b.spij = lambda d: (setattr(s, "t", s.t + d), advance())
    return s, b
def odrzut(s, b):
    return zdarzenia(s, "poscig_koniec")[0]

# 28a. prosty pościg: JEDNO naciśnięcie, brak stuknięć, brak odrzuceń, klawisz puszczony przy odl<=1
_random.seed(5)
s, b = swiat_trzymaj(cel_x=106)
r = start_poscig(s, b); k = odrzut(s, b)
sprawdz("30a trzymany klawisz: jedno naciśnięcie w prawo, bez stuknięć, dojście obok celu, klawisz puszczony",
        r is True and s.poz[0] == 105 and [z[1] for z in s.zd] == ["nacisnij", "puść"] and not s.taps and s.trzym is None
        and k["powod"] == "odl<=1" and k["tryb"] == "trzymaj" and k["odrzucone"] == 0 and k["kroki"] == 5, (s.zd, s.poz, k))
sprawdz("30a2 telemetria: trzymane_s, zmiany_kierunku, kroki_na_s", k["trzymane_s"] > 1.5 and k["zmiany_kierunku"] == 0
        and k["kroki_na_s"] > 1.4, k)
sprawdz("30a3 puls strażnika co obrót pętli", s.pulsy >= 10, s.pulsy)

# 28b. kroki/s: trzymanie vs stuknięcia (to samo opóźnienie kroku 0,45 s, ten sam koszt RPC)
ks_t, ks_s = [], []
for i in range(5):
    _random.seed(300 + i)
    s, b = swiat_trzymaj(cel_x=140); start_poscig(s, b); ks_t.append(odrzut(s, b)["kroki_na_s"])
    _random.seed(300 + i)
    s, b = swiat_poscigu(cel_x=140, opoznienie=0.45, koszt=KOSZT); b.spij = lambda d, s=s: setattr(s, "t", s.t + d)
    start_poscig(s, b); ks_s.append(zdarzenia(s, "poscig_koniec")[0]["kroki_na_s"])
mt, ms = sum(ks_t) / 5, sum(ks_s) / 5
print(f"     pomiar: kroki/s trzymanie {mt:.2f}, stuknięcia {ms:.2f} (krok gry 0,45 s = max {1/0.45:.2f})")
sprawdz("30b kroki/s: trzymanie >= 1,4 i >= 1,15x stuknięć z już przyspieszonej pętli (na żywo stuknięcia ~1,0)", mt >= 1.4 and mt >= 1.15 * ms, f"{mt:.2f} vs {ms:.2f}")

# 28c. zakręt: nowy klawisz naciśnięty PRZED puszczeniem starego (jedno zdarzenie "zmien", puszczenie dopiero przy wyjściu),
# bez zbędnych kroków (liczba kroków <= manhattan - 1 do pola obok)
_random.seed(7)
s, b = swiat_trzymaj(cel_x=108, cel_y=104)
start_poscig(s, b); k = odrzut(s, b)
puszczenia = [z for z in s.zd if z[1] == "puść"]
sprawdz("30c zakręty: zmiany kierunku bez puszczania, jedno puszczenie na końcu",
        k["zmiany_kierunku"] >= 1 and len(puszczenia) == 1 and s.zd[-1][1] == "puść" and any(z[1] == "zmien" for z in s.zd), s.zd)
sprawdz("30c2 dojście obok celu bez zbędnych kroków", max(abs(s.poz[0] - 108), abs(s.poz[1] - 104)) == 1
        and k["kroki"] <= (8 + 4) - 1, (s.poz, k))

# 28d. wyjścia puszczają klawisz: cel martwy w trakcie, HP, wstrzymanie, okno
for nazwa, ustaw in (("cel martwy", lambda s, b: s.stwory[0].__setitem__("hp", 0)),
                     ("spadek HP", lambda s, b: setattr(s, "hp", 80)),
                     ("pauza mózgu", lambda s, b: setattr(b, "_poscig_przerwanie", lambda: "wstrzymanie"))):
    s, b = swiat_trzymaj(cel_x=150)
    spij_o = b.spij
    def spij_hak(d, s=s, b=b, spij_o=spij_o, ustaw=ustaw):
        spij_o(d)
        if s.t > 1.2 and not getattr(s, "_ustawione", False):
            s._ustawione = True; ustaw(s, b)
    b.spij = spij_hak
    start_poscig(s, b); k = odrzut(s, b)
    sprawdz(f"30d {nazwa}: pętla wychodzi i klawisz jest puszczony", s.trzym is None and k["powod"] != "okno"
            and s.zd[-1][1] == "puść", (k["powod"], s.zd[-2:]))
s, b = swiat_trzymaj(cel_x=190)
start_poscig(s, b); k = odrzut(s, b)
sprawdz("30d2 limit okna: klawisz puszczony, okno dłuższe niż w stuknięciach (do POSCIG_TRZYMAJ_OKNO_DOBRY)",
        k["powod"] == "okno" and s.trzym is None and cavebot.POSCIG_OKNO_DOBRY < k["czas"] <= cavebot.POSCIG_TRZYMAJ_OKNO_DOBRY + 0.8, k)

# 28e. wyjątek / STOP / Ctrl+C w pętli: klawisz puszczony (try/finally), wyjątek leci dalej
for wyj in (bot.Zatrzymano("STOP"), KeyboardInterrupt(), RuntimeError("bum")):
    s, b = swiat_trzymaj(cel_x=150)
    spij_o = b.spij
    def spij_wyj(d, s=s, spij_o=spij_o, wyj=wyj):
        spij_o(d)
        if s.t > 1.5: raise wyj
    b.spij = spij_wyj
    try:
        start_poscig(s, b); lecial = None
    except BaseException as e:
        lecial = e
    sprawdz(f"30e {type(wyj).__name__} w pętli: klawisz puszczony, wyjątek propagowany",
            lecial is wyj and s.trzym is None and not b.w_poscigu, (lecial, s.zd[-2:]))

# 28f. ściana (brak ruchu): puść, jedno ponowne naciśnięcie, potem wyjście
s, b = swiat_trzymaj(cel_x=110, blokada=True)
start_poscig(s, b); k = odrzut(s, b)
sprawdz("30f ściana: naciśnięcie, puszczenie, jedno ponowienie, wyjście brak_ruchu, klawisz puszczony",
        k["powod"] == "brak_ruchu" and k["ponow_brak"] == cavebot.POSCIG_PONOW_BRAK and s.trzym is None
        and [z[1] for z in s.zd].count("nacisnij") == 1 + cavebot.POSCIG_PONOW_BRAK
        and k["czas"] < 2 * (cavebot.POSCIG_BRAK_ZMIANY + 0.3) + 0.3, (k, s.zd))

# 28g. stwór na polu przed nami: puszczamy z wyprzedzeniem, postać nie wchodzi na zajęte pole
s, b = swiat_trzymaj(cel_x=110)
mob = {"id": 77, "nazwa": "Troll", "gracz": False, "x": 103, "y": 100, "z": 7, "hp": 100}
s.stwory.append(mob); s.zajete = {(103, 100)}
b.ostatnie_stwory = [mob]
b.stwory = lambda wiek=None, m=mob: [m]
start_poscig(s, b); k = odrzut(s, b)
sprawdz("30g zajęte pole przed nami: klawisz puszczony zanim postać weszła (stoi na 102), brak wejścia na stwora",
        s.poz[0] <= 102 and s.trzym is None and ("puść", ) and any(z[1] == "puść" and z[0] < 3.0 for z in s.zd), (s.poz, s.zd, k["powod"]))

# 28h. pokrętło POSCIG_TRZYMAJ=False: stuknięcia (tryb "stuk") mimo metod trzymania w postaci
cavebot.POSCIG_TRZYMAJ = False
try:
    s, b = swiat_trzymaj(cel_x=106)
    s.postac_klawisze = []
    b.postac.klawisz = lambda kk: (s.taps.append(kk), None)[1]
    start_poscig(s, b); k = odrzut(s, b)
    sprawdz("30h POSCIG_TRZYMAJ=False: tryb stuk, bez trzymania", k["tryb"] == "stuk" and not s.zd and len(s.taps) >= 1, (k, s.taps))
finally:
    cavebot.POSCIG_TRZYMAJ = True

# 28i. skos trzymanym numpadem, gdy koszt skosu < 2 (domyślnie 3.0: wyłączone, tylko osie)
cavebot.POSCIG_SKOS_KOSZT = 1.5
try:
    s, b = swiat_trzymaj(cel_x=112, cel_y=106)
    def droga_osie(start, cel, blok=(), dlugosc=1, skosy=True, limit=None, znane=None):
        x, y = start[0], start[1]; wynik = []
        while max(abs(cel[0] - x), abs(cel[1] - y)) > dlugosc:
            if abs(cel[0] - x) >= abs(cel[1] - y): x += (cel[0] > x) - (cel[0] < x)
            else: y += (cel[1] > y) - (cel[1] < y)
            wynik.append((x, y, start[2]))
        return wynik
    b.mapa = types.SimpleNamespace(pole=lambda *a: (1, 0, 12), flagi=lambda *a: 1,
                                   przechodnie=lambda *a: True, droga=droga_osie)
    start_poscig(s, b)
    sprawdz("30i skos opłacalny: trzymany klawisz po skosie (1,1), potem osie, dojście obok celu",
            any(z[2] == (1, 1) for z in s.zd) and max(abs(s.poz[0] - 112), abs(s.poz[1] - 106)) == 1 and s.trzym is None, (s.zd, s.poz))
finally:
    cavebot.POSCIG_SKOS_KOSZT = 3.0
s, b = swiat_trzymaj(cel_x=112, cel_y=106)
start_poscig(s, b)
sprawdz("30i2 domyślny koszt skosu 3,0: tylko osie (brak skosu)", not any(z[2][0] and z[2][1] for z in s.zd), s.zd)

# 28j. start bota czyści klawisze (Cavebot.__init__ woła postac.puszcz_wszystko)
wolane_czysc = []
sw = Swiat(); pp = P(sw); pp.puszcz_wszystko = lambda: wolane_czysc.append(1)
zrob_pp = cavebot.Cavebot(pp, [(100 + i, 100, 7) for i in range(1, 5)], okrazenia=1, spij=sw.spij, zegar=sw.zegar)
sprawdz("30j start bota: puszcz_wszystko wywołane raz", wolane_czysc == [1])

# 28k. oscylacja lewo-prawo (cel zygzakuje, kierunek podąża za jego kolumną): brak ping-pongu A-B-A, postęp do przodu
def _symuluj_cel(start, ruch_celu, okres=0.45, ziarno=2):
    _random.seed(ziarno)
    s, b = swiat_trzymaj(cel_x=start[0], cel_y=start[1])
    s.poz[0], s.poz[1] = 100, 100
    m = s.stwory[0]; m["hp"] = 10
    st = {"n": 0, "next": okres}
    spij0 = b.spij
    def spij(d):
        spij0(d)
        while s.t >= st["next"]:
            st["n"] += 1; st["next"] += okres
            nx, ny = ruch_celu(st["n"], (m["x"], m["y"]))
            if (nx, ny) != tuple(s.poz): m["x"], m["y"] = nx, ny
    b.spij = spij
    slad = []
    poz0 = b.postac.pozycja
    def pozycja():
        p = poz0()
        if not slad or slad[-1] != p: slad.append(p)
        return p
    b.postac.pozycja = pozycja
    start_poscig(s, b)
    return s, b, slad, odrzut(s, b)
def pingpongi(slad): return sum(1 for i in range(2, len(slad)) if slad[i][:2] == slad[i - 2][:2])
s, b, slad, k = _symuluj_cel((102, 96), lambda n, c: (100 + (2 if n % 2 else -2), c[1] - (1 if n % 2 == 0 else 0)))
sprawdz("31a cel zygzakuje o 2 kolumny: brak ping-pongu A-B-A, >= 13 pól do przodu, klawisz puszczony",
        pingpongi(slad) == 0 and (100 - s.poz[1] >= 13 or k["powod"] == "odl<=1") and s.trzym is None
        and k["powod"] != "oscylacja", (pingpongi(slad), s.poz, k["powod"], slad))   # 12.10: z dociskaniem cel bywa dopadnięty wcześniej
s, b, slad, k = _symuluj_cel((102, 98), lambda n, c: c)
sprawdz("31b cel stoi 2 pola po skosie: dwa kroki bez zawracania, odl<=1", k["powod"] == "odl<=1" and k["kroki"] == 2
        and pingpongi(slad) == 0, (k, slad))
s, b, slad, k = _symuluj_cel((108, 95), lambda n, c: c)
sprawdz("31c cel stoi daleko po skosie (na skraju ekranu): dojście obok, brak ping-pongu, minimalna liczba kroków",
        k["powod"] == "odl<=1" and pingpongi(slad) == 0 and k["kroki"] <= 8 + 5 - 1, (k, slad))
s, b, slad, k = _symuluj_cel((101, 95), lambda n, c: (c[0] + (1 if n % 2 else -1), c[1] - (0 if n % 2 else 1)))
sprawdz("31d cel zygzakuje o 1 kolumnę: kroki rosną w stronę celu, brak ping-pongu", pingpongi(slad) == 0 and k["kroki"] >= 5
        and s.poz[1] <= 96, (k, slad))

# 31e. filtr kierunku jednostkowo: zakaz cofnięcia na świeżo opuszczone pole i histereza zmiany osi
s, b = swiat_trzymaj(cel_x=130)
stab = {"ost": (1, 0), "t_zm": 0.0, "hist": [(104, 100, 9.0), (105, 100, 9.6)]}
w, pw = b._poscig_stabilny((-1, 0), (105, 100, 7), (110, 98), (1, 0), set(), stab, 10.0)
sprawdz("31e1 cofnięcie na pole sprzed 1 s zabronione (kierunek nie jest w lewo)", w != (-1, 0) and pw is not None, (w, pw))
stab = {"ost": (0, -1), "t_zm": 9.8, "hist": [(105, 100, 5.0)]}
w, pw = b._poscig_stabilny((1, 0), (105, 100, 7), (108, 94), (0, -1), set(), stab, 10.0)
sprawdz("31e2 histereza: zmiana osi <0,4 s po poprzedniej zmianie odrzucona, trzymamy Up", w == (0, -1) and pw == "histereza", (w, pw))
stab = {"ost": (0, -1), "t_zm": 0.0, "hist": [(105, 100, 5.0)]}
w, pw = b._poscig_stabilny((1, 0), (105, 100, 7), (110, 94), (0, -1), set(), stab, 10.0)
sprawdz("31e3 histereza nie blokuje zmiany osi, gdy cel jest >= 3 pola w bok", w == (1, 0) and pw is None, (w, pw))
sprawdz("31e4 przewidywanie celu tylko przy marszu prosto",
        b._poscig_cel_przewidziany([(120, 100), (120, 99), (120, 98)], (120, 98), (105, 100, 7)) == (120, 97)
        and b._poscig_cel_przewidziany([(120, 100), (121, 100), (121, 99)], (121, 99), (105, 100, 7)) == (121, 99)
        and b._poscig_cel_przewidziany([(107, 100), (107, 99), (107, 98)], (107, 98), (105, 100, 7)) == (107, 98))

# 31f. wykrycie oscylacji: wymuszone Left/Right na przemian (filtr wyłączony) -> wyjście "oscylacja", klawisz puszczony,
# potem 5 s pościgu stuknięciami (tryb "stuk"), a po tym czasie znowu trzymanie
s, b = swiat_trzymaj(cel_x=130, cel_y=100)
licznik = [0]
def decyzja_lr(st, poz, v, zaj):
    licznik[0] += 1
    return ((-1, 0) if licznik[0] % 2 else (1, 0)), False, None
b._poscig_decyzja = decyzja_lr
b._poscig_stabilny = lambda want, *a: (want, None)
b.postac.klawisz = lambda kk: s.taps.append(kk)
start_poscig(s, b); k = odrzut(s, b)
sprawdz("31f wykryta oscylacja: powód 'oscylacja' w < 4 s, klawisz puszczony", k["powod"] == "oscylacja" and s.trzym is None
        and k["czas"] < 4.5 and s.zd[-1][1] == "puść", (k["powod"], k["czas"], s.zd))
sprawdz("31f2 po oscylacji tryb stuknięć na POSCIG_STUK_PO_OSCYLACJI s", not b._poscig_trzymaj_mozliwe()
        and abs(b.poscig_stuk_do - (s.t + cavebot.POSCIG_STUK_PO_OSCYLACJI)) < 1.0, b.poscig_stuk_do)
s.t = b.poscig_stuk_do + 0.1
sprawdz("31f3 po upływie okna znowu trzymanie", b._poscig_trzymaj_mozliwe())

# 32. sekwencje odtworzone z telemetrii 11.10 14:41-14:44 (pole `sciezka`): zawracanie i cofnięcia kroków przez serwer
# 32a. 14:41:00: korytarz, gracz (32000,32133), cel na wschodzie; pole sprzed 1,3 s jest "za nami", a z przodu zajęte -> wyjście, nie ping-pong
s, b = swiat_trzymaj(cel_x=130)
hist = [(31998, 32132, 0.0), (31999, 32132, 0.29), (32000, 32132, 1.83), (32001, 32133, 2.22), (32000, 32133, 3.56)]
stab = {"ost": (-1, 0), "t_zm": 3.5, "hist": hist}
w, pw = b._poscig_stabilny((1, 0), (32000, 32133, 11), (32010, 32133), (-1, 0), {(32001, 32134)}, stab, 3.6)
sprawdz("32a zawracanie na pole sprzed 1,4 s bez innej drogi do celu: wyjście 'zawroc' (nie krok od celu)", w is None and pw == "zawroc", (w, pw))
# 32b. 14:42:06: pościg za uciekającym, gryzący szczur z tyłu: A-B-A przy powrocie na (32006,32140) po 0,6 s
hist = [(32006, 32139, 3.47), (32006, 32140, 4.01), (32007, 32140, 4.59)]
stab = {"ost": (1, 0), "t_zm": 4.0, "hist": hist}
w, pw = b._poscig_stabilny((-1, 0), (32007, 32140, 11), (32000, 32137), (1, 0), set(), stab, 4.7)
sprawdz("32b cel na zachodzie, ale pole z zachodu opuszczone 0,7 s temu: pole omijamy osią Y do celu", w == (0, -1) and pw == "pingpong", (w, pw))

# 32c. 14:43:47: krok na (32020,32150) cofnięty przez serwer po 0,09 s (stwór wszedł na pole): nie próbujemy w kółko
class CofajacySwiat: pass
def swiat_cofniec(pole, cel_x=112):
    s, b = swiat_trzymaj(cel_x=cel_x, cel_y=100)
    s.cofnij = {pole}; s.cofnij_o = None; s.cofniec = 0
    adv0 = None
    def advance2():
        if s.cofnij_o is not None and s.t >= s.cofnij_o[0]:
            s.poz[0], s.poz[1] = s.cofnij_o[1]; s.cofnij_o = None; s.cofniec += 1
        while s.krok is not None and s.t >= s.krok[0] + s.opoznienie:
            tc, v = s.krok[0] + s.opoznienie, s.krok[1]
            nx, ny = s.poz[0] + v[0], s.poz[1] + v[1]
            if (nx, ny) == (s.stwory[0]["x"], s.stwory[0]["y"]):
                pass
            elif (nx, ny) in s.cofnij and s.cofnij_o is None:
                s.cofnij_o = (tc + 0.09, (s.poz[0], s.poz[1])); s.poz[0], s.poz[1] = nx, ny
                s.pozycje_czasy.append(tc)
            elif s.cofnij_o is None:
                s.poz[0], s.poz[1] = nx, ny; s.pozycje_czasy.append(tc)
            s.krok = (tc, s.trzym) if s.trzym else None
    p = b.postac
    def tk(dx, dy):
        advance2(); s.zd.append((round(s.t, 3), "zmien" if s.trzym else "nacisnij", (dx, dy)))
        s.trzym = (dx, dy)
        if s.krok is None: s.krok = (s.t, s.trzym)
    def pu():
        advance2()
        if s.trzym is not None: s.zd.append((round(s.t, 3), "puść", s.trzym))
        s.trzym = None
    def po():
        s.t += 0.035; advance2(); return tuple(s.poz)
    p.trzymaj_kierunek = tk; p.puszczaj = pu; p.pozycja = po
    b.spij = lambda d: (setattr(s, "t", s.t + d), advance2())
    return s, b
s, b = swiat_cofniec((104, 100), cel_x=112)
b.ostatnie_stwory = []
start_poscig(s, b); k = odrzut(s, b)
sprawdz("32c krok cofnięty przez serwer: pole zablokowane na POSCIG_BLOK_S, <= 2 cofnięcia, klawisz puszczony, brak pętli do końca okna",
        s.trzym is None and s.cofniec <= 2 and k["czas"] < 8.0 and k["powod"] in ("oscylacja", "zawracanie", "brak_ruchu", "objazd", "odl<=1"),
        (s.cofniec, k["powod"], k["czas"], k.get("cofniecia"), s.zd[-6:]))
sprawdz("32c2 po cofnięciach telemetria ma ścieżkę z pozycją celu", isinstance(k.get("sciezka"), list) and len(k["sciezka"]) >= 1
        and len(k["sciezka"][0]) == 6, k.get("sciezka"))


# 33. pościg na pamięć: ranny cel zniknął z widoku żywy (prawdziwa mapa, korytarz y=32142 x=32008..32017 + jaskinia na północ)
if _mapa_mod.PLIK_MAPY.is_file():
    MAPA33 = _mapa_mod.Mapa()
    WOLNE33 = [(x, y) for x in range(32000, 32070) for y in range(32128, 32170)
               if MAPA33.flagi(x, y, 11) & 1 and MAPA33.przechodnie(x, y, 11) is not False]
    TRASA33 = [tuple(p) for p in __import__("json").loads((cavebot.KATALOG_TRAS / "kanaly2.json").read_text())]
    def swiat33(poz=(32008, 32142, 11), rat_x=32015, hp=20, ukryj_o=0.6, ukryta=(32017, 32138), widac=3,
                wroc=True, drugi=None, exp=None):
        """Szczur ucieka na wschód korytarzem 1 pole / 0,5 s; po `ukryj_o` s znika z listy (wyszedł z widoku) na
        polu `ukryta` i wraca na listę, gdy gracz jest bliżej niż `widac` pól (wroc=False: nigdy)."""
        s = Swiat(poz=poz); s.t = 0.0
        b = zrob_lab(s, TRASA33, klik=True, mapa=MAPA33, okrazenia=1)
        s.wolne = set(WOLNE33); b.znane |= {(x, y, 11) for x, y in WOLNE33}
        s.zabija = False
        s.rat = dict(szczur(3301, rat_x, hp=hp, y=32142), z=11); s.stwory = [s.rat]
        s.ukryty = False; s.zdarz = []; s.exp = exp
        if drugi: s.stwory.append(drugi)
        b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: s.zdarz.append((typ, d)), probka=lambda *a: None, linia=lambda *a: None)
        zap0 = s.zapytaj
        def zap(z):
            r = zap0(z)
            if z["cmd"] == "gracz" and s.exp is not None: r["gracz"]["exp"] = s.exp
            return r
        s.zapytaj = zap; b.zapytaj = zap
        s.faza = 0
        def swiat(i):
            if s.faza == 1:
                if wroc and max(abs(s.poz[0] - ukryta[0]), abs(s.poz[1] - ukryta[1])) <= widac:
                    s.faza = 2; s.rat["x"], s.rat["y"] = ukryta; s.stwory.append(s.rat)
            elif s.faza == 0 and s.t >= ukryj_o:
                s.faza = 1; s.rat["x"], s.rat["y"] = 32016, 32142
                s.stwory[:] = [m for m in s.stwory if m is not s.rat]
            elif s.faza == 0 and s.t > 0:
                s.rat["x"] = min(32016, 32015 + int(s.t / 0.5))
        return s, b, swiat
    def zdarz33(s, typ): return [d for t, d in s.zdarz if t == typ]

    # 33a. cel ucieka korytarzem poza ekran: bot idzie za nim po mapie i go odnajduje
    cavelog.clear()
    s, b, sw = swiat33()
    bieg(b, s, 120, sw)
    st, ko = zdarz33(s, "poscig_pamiec_start"), zdarz33(s, "poscig_pamiec_koniec")
    sprawdz("33a zniknął żywy: start pościgu na pamięć z ostatnią pozycją i wektorem na wschód",
            len(st) == 1 and st[0]["id"] == 3301 and st[0]["poz"][1] == 32142 and st[0]["wektor"][0] > 0
            and st[0]["hp"] == 20 and st[0]["limit_s"] == cavebot.POSCIG_PAMIEC_S, st)
    sprawdz("33a2 bot idzie za nim i go odnajduje: koniec 'odnaleziony', kroki > 0, bot dalej na wschód",
            len(ko) == 1 and ko[0]["wynik"] == "odnaleziony" and ko[0]["kroki"] >= 3 and s.poz[0] >= 32014
            and b.pamiec is None, (ko, s.poz))
    sprawdz("33a3 po odnalezieniu wraca normalna walka z tym samym id (Nowy cel w logu po zniknięciu)",
            any("zniknął z widoku żywy" in l for l in cavelog) and any("odnaleziony po zniknięciu" in l for l in cavelog)
            and any("Nowy cel: Rat" in l for l in cavelog[[i for i, l in enumerate(cavelog) if "odnaleziony" in l][0]:]),
            [l for l in cavelog if "Rat" in l][-6:])

    # 33b. cel znika, bo został zabity: obok nas (odl 1) albo exp wzrósł => brak pościgu na pamięć
    s, b, sw = swiat33(rat_x=32009, hp=20, ukryj_o=99)
    s.zabija = True
    for i in range(8):
        b.tick()
        s.stwory[:] = [m for m in s.stwory if m["hp"] > 0]       # zwłoki znikają z listy
    sprawdz("33b cel zabity obok: brak pościgu na pamięć, loot",
            not zdarz33(s, "poscig_pamiec_start") and b.pamiec is None and b.lootlog, (s.zdarz, b.lootlog))
    s, b, sw = swiat33(exp=1000)
    for i in range(30):
        sw(i)
        if s.faza == 1 and s.exp == 1000: s.exp = 1020          # exp wzrósł w chwili zniknięcia
        b.tick()
    sprawdz("33b2 zniknął z widoku, ale exp wzrósł => zabity: brak pościgu na pamięć",
            not zdarz33(s, "poscig_pamiec_start") and b.pamiec is None, s.zdarz)

    # 33c. inne gryzące moby obok => nie wchodzi w pościg na pamięć
    s, b, sw = swiat33(drugi=dict(szczur(3302, 32009, hp=100, y=32142), z=11))
    for i in range(40):
        sw(i); b.tick()
        if s.stwory and any(m["id"] == 3302 for m in s.stwory):
            s.hp = max(40, s.hp - 3)                            # świeży szczur obok gryzie
    sprawdz("33c świeży mob obok gryzie: brak pościgu na pamięć", not zdarz33(s, "poscig_pamiec_start"), s.zdarz)

    # 33d. limit czasu: cel nie wraca, po POSCIG_PAMIEC_S s koniec i powrót do trasy
    cavelog.clear()
    s, b, sw = swiat33(wroc=False)
    t_start = []
    for i in range(200):
        sw(i)
        if not b.tick(): break
        if b.pamiec and not t_start: t_start.append(s.t)
    ko = zdarz33(s, "poscig_pamiec_koniec")
    sprawdz("33d limit czasu: koniec 'limit', bot wraca do trasy (pamięć wyczyszczona, stan IDZ)",
            len(ko) == 1 and ko[0]["wynik"] == "limit" and b.pamiec is None and b.cel is None
            and ko[0]["czas"] <= cavebot.POSCIG_PAMIEC_S + 2.5 and b.stan in ("IDZ", "POGON"), (ko, b.stan))
    sprawdz("33d2 przy limicie bot nie przekracza POSCIG_PAMIEC_POL pól za ostatnią pozycją",
            ko and ko[0]["kroki"] > 0 and max(abs(s.poz[0] - 32016), abs(s.poz[1] - 32142)) <= cavebot.POSCIG_PAMIEC_POL + 6,
            (s.poz, ko))

    # 33e. wyłączony (POSCIG_PAMIEC=False): jak dawniej, bez pościgu
    cavebot.POSCIG_PAMIEC = False
    try:
        s, b, sw = swiat33()
        bieg(b, s, 40, sw)
        sprawdz("33e POSCIG_PAMIEC=False: brak zdarzeń pościgu na pamięć", not zdarz33(s, "poscig_pamiec_start") and b.pamiec is None, s.zdarz)
    finally:
        cavebot.POSCIG_PAMIEC = True

    # 33d3. limit czasu w czystej postaci: POSCIG_PAMIEC_S s mija, zanim bot dojdzie do końca korytarza
    cavebot.POSCIG_PAMIEC_S = 1.0
    try:
        s, b, sw = swiat33(wroc=False)
        bieg(b, s, 60, sw)
        ko = zdarz33(s, "poscig_pamiec_koniec")
        sprawdz("33d3 limit POSCIG_PAMIEC_S: koniec 'limit' z powodem czas, pamięć wyczyszczona",
                len(ko) == 1 and ko[0]["wynik"] == "limit" and ko[0]["powod"] == "czas" and b.pamiec is None
                and 1.0 <= ko[0]["czas"] <= 2.5, ko)
    finally:
        cavebot.POSCIG_PAMIEC_S = 7.0

    # 33f. w trakcie pościgu: HP gracza spada (ale jeszcze nie ucieczka) => przerwany; wejście zablokowane przy niskim HP
    s, b, sw = swiat33(wroc=False); s.hp = 58
    for i in range(60):
        sw(i)
        if b.pamiec and s.hp == 58: s.hp = 54
        b.tick()
    ko = zdarz33(s, "poscig_pamiec_koniec")
    sprawdz("33f spadek HP w pościgu: koniec 'przerwany' (hp_prog/gryzie)",
            ko and ko[0]["wynik"] == "przerwany" and ko[0]["powod"] in ("hp_prog", "gryzie"), ko)
    s, b, sw = swiat33()
    s.hp = 50; s.max_hp = 100
    for i in range(30):
        sw(i); b.tick()
    sprawdz("33f2 HP gracza <= próg+15: brak wejścia w pościg", not zdarz33(s, "poscig_pamiec_start"), s.zdarz)

    # 33g. koniec korytarza: najdalsze pole wzdłuż wektora, nie dalej niż POSCIG_PAMIEC_POL od ostatniej pozycji
    s, b, sw = swiat33()
    e = b._pamiec_koniec_korytarza((32012, 32142, 11), (1, 0), 4)
    e2 = b._pamiec_koniec_korytarza((32012, 32142, 11), (1, 0), 9)
    e0 = b._pamiec_koniec_korytarza((32012, 32142, 11), (0, 0), 9)
    sprawdz("33g koniec korytarza: w stronę wektora, w limicie pól, na polu przechodnim",
            e[0] > 32012 and max(abs(e[0] - 32012), abs(e[1] - 32142)) <= 4 and e in set(WOLNE33)
            and e2 in set(WOLNE33) and max(abs(e2[0] - 32012), abs(e2[1] - 32142)) <= 9 and e0 == (32012, 32142),
            (e, e2, e0))

# 34. seria "zawracanie" 15:06:30-15:06:52 (telemetria 11.10): kolejne pętle z historią 3, 2, 1, 0 kroków. Cel zmienia stronę
# w trakcie PIERWSZEGO kroku, więc "powrót" na pole startowe to nie oscylacja: wyjście bez kary 3 s + 5 s stuknięć.
def swiat34(kroki_hist=0):
    s, b = swiat_trzymaj(cel_x=108)
    spij_o = b.spij
    def hak(d):
        spij_o(d)
        if not getattr(s, "_przeniesiony", False) and s.t > 0.12 + 0.1 * kroki_hist and s.zd:
            s._przeniesiony = True; s.stwory[0]["x"] = s.poz[0] - 4   # cel przeskakuje na drugą stronę
    b.spij = hak
    return s, b
b_t = None
for n in (0, 1):
    _random.seed(40 + n)
    s, b = swiat34(n)
    b.ostatnie_stwory = []
    t_przed = b.zegar()
    start_poscig(s, b); k = odrzut(s, b)
    sprawdz(f"34a{n} zawrócenie na krótkiej historii: wyjście 'zawracanie' (cel za nami), klawisz puszczony",
            k["powod"] == "zawracanie" and s.trzym is None, (k["powod"], s.zd))
    sprawdz(f"34b{n} krótka historia: brak 3 s przerwy i 5 s stuknięć (poscig_przerwa_do/stuk_do nietknięte)",
            b.poscig_przerwa_do == float("-inf") and b.poscig_stuk_do == float("-inf"),
            (b.poscig_przerwa_do, b.poscig_stuk_do))
# po takim wyjściu następny pościg rusza od razu (nie ma blokady przerwy)
sprawdz("34c po krótkim zawróceniu _poscig_trzymaj_mozliwe nadal True (trzymanie, nie stuknięcia)", b._poscig_trzymaj_mozliwe())
# długa historia (>= POSCIG_ZAWR_MIN_HIST pól) nadal karana jak dawniej: ochrona przed prawdziwą oscylacją zostaje
s, b = swiat_trzymaj(cel_x=130)
b.ostatnie_stwory = []
stab = {"ost": (1, 0), "t_zm": 0.0, "hist": [(100, 100, 9.0), (101, 100, 9.4), (102, 100, 9.8), (103, 100, 10.0)]}
w, pw = b._poscig_stabilny((-1, 0), (103, 100, 7), (90, 100), (1, 0), set(), stab, 10.1)
sprawdz("34d długa historia: filtr dalej zgłasza 'zawroc' (kara zostaje), tu 4 pola >= POSCIG_ZAWR_MIN_HIST",
        w is None and pw == "zawroc" and len(stab["hist"]) >= cavebot.POSCIG_ZAWR_MIN_HIST, (w, pw))

# 35. ATAK_TYLKO_PRZY_CELU: do 8 lvla atak działa tylko przy dystansie <= 1; z dystansu ani klików, ani czekania na weryfikację
cavebot.ATAK_TYLKO_PRZY_CELU = True
def dyst35(b, a, g): return max(abs(a["x"] - g["x"]), abs(a["y"] - g["y"]))
# 35a. ponow_atak z dystansu 2+: zero klików, zero pytań o flagę, zero spij, brak weryfikacji; cel obok: klik po 2 odczytach False
s = Swiat(); s.stwory = [szczur(980, 105, hp=10)]
b = zrob(s, trasa()); s.zabija = False
zap35 = []; b.czy_atakowany = lambda st, g: (zap35.append(1), False)[1]
c = dict(s.stwory[0]); poz = tuple(s.poz); t0 = s.t
wyn = []
for odl in (5, 3, 2, 5, 2, 4):
    c["x"] = poz[0] + odl
    for _ in range(4):
        s.t += 3.0; wyn.append(b.ponow_atak(c, poz))
sprawdz("35a ponow_atak z dystansu 2+ (24 wywołania): zero klików, zero zapytań o flagę, brak weryfikacji",
        not any(wyn) and s.ataki == [] and zap35 == [] and b.atak_weryf is None, f"ataki={len(s.ataki)} zap={len(zap35)}")
c["x"] = poz[0] + 1
r1 = b.ponow_atak(c, poz); r2 = b.ponow_atak(c, poz)
sprawdz("35a2 po zbliżeniu do dystansu 1: klik od razu po 2 odczytach False (bez dodatkowych pauz)",
        r1 is False and r2 is True and len(s.ataki) == 1, f"r1={r1} r2={r2} ataki={len(s.ataki)}")
s.t += 0.5; r3 = b.ponow_atak(c, poz)
sprawdz("35a3 weryfikacja po kliku z dystansu 1 działa jak dawniej (klik cofający, gdy flaga nadal False)",
        r3 is True and len(s.ataki) == 2, f"ataki={len(s.ataki)}")
# 35b. ochrona przed wyłączeniem ataku: flaga True przy celu obok = brak kliku
s = Swiat(); s.stwory = [szczur(981, 101, hp=10)]
b = zrob(s, trasa()); s.zabija = False; b.czy_atakowany = lambda st, g: True
c = dict(s.stwory[0]); poz = tuple(s.poz)
for _ in range(5): s.t += 3.0; b.ponow_atak(c, poz)
sprawdz("35b cel obok, flaga ataku True: brak kliku (klik wyłączyłby atak)", s.ataki == [], f"ataki={len(s.ataki)}")
# 35c. walcz: potwór stoi 5 pól dalej (nie podchodzi): żaden klik z dystansu > 1, pierwszy klik zaraz po dojściu obok
s = Swiat(); s.stwory = [{"id": 36, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1); s.zabija = False
atak0 = b.atak; odl_klik = []; t_klik = []
def atak35(m, g): odl_klik.append(dyst35(b, m, g)); t_klik.append(s.t); atak0(m, g)
b.atak = atak35
t_obok = [None]; pierwszy_obok = []
def obserwuj(i):
    if t_obok[0] is None and s.poz[0] >= 104: t_obok[0] = s.t
bieg(b, s, 40, obserwuj)
sprawdz("35c walcz: wszystkie kliki ataku przy dystansie <= 1 (zero z dystansu 2+)",
        odl_klik and all(o <= 1 for o in odl_klik), f"odl={odl_klik} poz={s.poz}")
sprawdz("35c2 pierwszy klik zaraz po dojściu obok celu (<= 1,5 s)",
        t_obok[0] is not None and t_klik and 0 <= t_klik[0] - t_obok[0] <= 1.5, f"t_obok={t_obok[0]} kliki={t_klik[:3]}")
# 35d. pościg trzymanym klawiszem za uciekającym (flaga ataku False): bez klików ani blokujących pauz do dystansu 1
for przelacznik in (True, False):
    cavebot.ATAK_TYLKO_PRZY_CELU = przelacznik
    _random.seed(7)
    s, b = swiat_trzymaj(cel_x=108)
    b.ostatnie_stwory = []; kl35 = []
    b.czy_atakowany = lambda st, g: False
    atak_b = b.atak
    b.atak = lambda m, g: (kl35.append(dyst35(b, m, g)), atak_b(m, g))
    r = start_poscig(s, b); k = odrzut(s, b)
    if przelacznik:
        sprawdz("35d pościg: zero klików ataku z dystansu 2+, dojście obok (odl<=1)",
                kl35 == [] and k["powod"] == "odl<=1" and s.poz[0] == 107, (kl35, k["powod"], s.poz))
    else:
        sprawdz("35d2 kontrola: przełącznik False przywraca dawne klikanie z dystansu w pościgu",
                any(o >= 2 for o in kl35), kl35)
cavebot.ATAK_TYLKO_PRZY_CELU = False

# 36. loot w walce (LOOT_W_WALCE): jeden atomowy krok lootu na obieg, gdy atak trwa, cel obok, <= 2 stykających, HP >= 70%
cavebot.ATAK_TYLKO_PRZY_CELU = True
def swiat36(obok=1, hp=100, flaga=True, zwloki=(100, 101, 7), kroki=("otwarcie", "przenies gold coin", "weryfikacja")):
    s = Swiat(hp=hp); s.zabija = False
    poz_mob = [(101, 100), (101, 101), (99, 100), (99, 99)]
    s.stwory = [{"id": 40 + i, "nazwa": "Rat", "gracz": False, "x": poz_mob[i][0], "y": poz_mob[i][1], "z": 7, "hp": 100}
                for i in range(obok)]
    b = zrob(s, trasa(), okrazenia=1)
    b.czy_atakowany = lambda st, g: s.flaga36
    s.flaga36 = flaga
    wyw = []; ev = []; zam = []
    def krok(stan, zw, poz, log=print):
        wyw.append((len(b.zwloki_czekajace), tuple(zw), tuple(poz), s.t))
        i = stan.setdefault("i", 0); stan["i"] = i + 1
        if hasattr(s, "po_kroku") and s.po_kroku: s.po_kroku(i, stan)
        if i < len(kroki): stan["faza"] = "przenies"; return "kontynuuj", kroki[i]
        return "gotowe", "ok"
    b.loot.krok_w_walce = krok
    b.loot.zamknij_w_walce = lambda stan, log=print: zam.append(1) or True
    b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: ev.append((typ, d)), probka=lambda *a: None)
    if zwloki is not None:
        b.zwloki_czekajace = [(tuple(zwloki), s.t)]
    return s, b, wyw, ev, zam
def licz_ticki36(b, s, n=40):
    ticki = []
    for _ in range(n):
        if not b.tick(): break
        ticki.append(s.t)
    return ticki
# 36a. 1 stykający, flaga True, HP 100: kroki lootu w walce, po jednym na obieg, zwłoki zdjęte z listy po zakończeniu
s, b, wyw, ev, zam = swiat36()
licz_ticki36(b, s)
sprawdz("36a loot w walce: wszystkie 4 wywołania kroku (3 kroki + zakończenie)", len(wyw) == 4, f"wyw={len(wyw)}")
sprawdz("36a2 zwłoki zdjęte z listy odłożonych po 'gotowe'", b.zwloki_czekajace == [], b.zwloki_czekajace)
czasy = [w[3] for w in wyw]
sprawdz("36a3 kroki w osobnych obiegach (odstęp > 0 s, każdy tick = pomiędzy czymś)", all(y > x for x, y in zip(czasy, czasy[1:])), czasy)
sprawdz("36a4 zero Alt+klików w zwłoki: ataki tylko w potwory (id 40)", s.ataki and all(a[0] == 40 for a in s.ataki), s.ataki[:3])
sprawdz("36a5 telemetria: 3x loot_w_walce_krok + koniec",
        [e[0] for e in ev].count("loot_w_walce_krok") == 4 and not any(e[0] == "loot_w_walce_przerwany" for e in ev), [e[0] for e in ev])
sprawdz("36a6 krok woła się z pozycją gracza przy zwłokach (odl 1)",
        all(max(abs(w[1][0] - w[2][0]), abs(w[1][1] - w[2][1])) == 1 for w in wyw), wyw[:1])
# 36b. 3 stykających: brak lootu w walce
s, b, wyw, ev, zam = swiat36(obok=3)
licz_ticki36(b, s)
sprawdz("36b 3 stykających: brak kroków lootu w walce", wyw == [] and len(b.zwloki_czekajace) == 1, f"wyw={len(wyw)}")
# 36b2. 2 stykających: jeszcze wolno
s, b, wyw, ev, zam = swiat36(obok=2)
licz_ticki36(b, s)
sprawdz("36b2 2 stykających: loot w walce działa", len(wyw) >= 1, f"wyw={len(wyw)}")
# 36c. HP < 70%
s, b, wyw, ev, zam = swiat36(hp=50)
licz_ticki36(b, s, 25)
sprawdz("36c HP 50% (<= próg + margines lootu 15): brak lootu w walce", wyw == [], f"wyw={len(wyw)}")
# 36d. flaga ataku False
s, b, wyw, ev, zam = swiat36(flaga=False)
licz_ticki36(b, s, 25)
sprawdz("36d flaga ataku False: brak lootu w walce", wyw == [], f"wyw={len(wyw)}")
# 36e. stoimy na zwłokach
s, b, wyw, ev, zam = swiat36(zwloki=(100, 100, 7))
licz_ticki36(b, s, 25)
sprawdz("36e stoimy na zwłokach: brak lootu w walce", wyw == [], f"wyw={len(wyw)}")
# 36f. zwłoki dalej niż 1 pole
s, b, wyw, ev, zam = swiat36(zwloki=(100, 102, 7))
licz_ticki36(b, s, 25)
sprawdz("36f zwłoki w odl 2: brak lootu w walce (tylko odl 1)", wyw == [], f"wyw={len(wyw)}")
# 36g. przełącznik LOOT_W_WALCE=False i pauza mózgu
cavebot.LOOT_W_WALCE = False
s, b, wyw, ev, zam = swiat36()
licz_ticki36(b, s, 25)
cavebot.LOOT_W_WALCE = True
sprawdz("36g LOOT_W_WALCE=False: brak lootu w walce", wyw == [], f"wyw={len(wyw)}")
s, b, wyw, ev, zam = swiat36()
b._poscig_przerwanie = lambda: "rozmowa"
licz_ticki36(b, s, 25)
sprawdz("36g2 pauza/rozmowa mózgu: brak lootu w walce", wyw == [], f"wyw={len(wyw)}")
# 36h. przerwanie w trakcie: HP spada poniżej 70% po pierwszym kroku -> przerwany (hp / hp_spadek), okno nie zamykane (pilne)
s, b, wyw, ev, zam = swiat36(kroki=("otwarcie",) + ("przenies x",) * 20)
def po_kroku(i, stan):
    if i == 1: s.hp = 55
s.po_kroku = po_kroku
licz_ticki36(b, s, 30)
prz = [e for e in ev if e[0] == "loot_w_walce_przerwany"]
sprawdz("36h spadek HP poniżej 70% w trakcie: przerwanie z powodem hp/hp_spadek/ucieczka, zwłoki zostają na liście",
        len(prz) == 1 and prz[0][1]["powod"] in ("hp", "hp_spadek", "ucieczka") and len(b.zwloki_czekajace) == 1 and len(wyw) <= 3,
        (prz, len(wyw), b.zwloki_czekajace))
# 36i. trzeci potwór dochodzi w trakcie: przerwanie "stykajace"
s, b, wyw, ev, zam = swiat36(kroki=("otwarcie",) + ("przenies x",) * 20)
def dolacza(i, stan):
    if i == 1:
        s.stwory += [{"id": 50, "nazwa": "Rat", "gracz": False, "x": 99, "y": 100, "z": 7, "hp": 100},
                     {"id": 51, "nazwa": "Rat", "gracz": False, "x": 99, "y": 99, "z": 7, "hp": 100}]
s.po_kroku = dolacza
licz_ticki36(b, s, 30)
prz = [e for e in ev if e[0] == "loot_w_walce_przerwany"]
sprawdz("36i trzeci stykający w trakcie: przerwanie 'stykajace', bez zamykania okna (pilne)",
        len(prz) == 1 and prz[0][1]["powod"] == "stykajace" and zam == [], (prz, zam))
# 36j. flaga ataku zgasła po naszym kliku w zwłoki: kara, loot w walce wstrzymany
s, b, wyw, ev, zam = swiat36(kroki=("otwarcie",) + ("przenies x",) * 20)
def gasi(i, stan):
    if i == 1: s.flaga36 = False
s.po_kroku = gasi
licz_ticki36(b, s, 30)
prz = [e for e in ev if e[0] == "loot_w_walce_przerwany"]
sprawdz("36j atak wyłączony kliknięciem w zwłoki: kara 1, powód atak_wylaczony, loot wstrzymany",
        b.lww_kary == 1 and prz and prz[0][1]["powod"] == "atak_wylaczony" and b.lww_kara_do > s.t, (b.lww_kary, prz))
# 36k. cel poza zasięgiem w trakcie: zwykłe przerwanie, okno zamykane (niepilne)
s, b, wyw, ev, zam = swiat36(kroki=("otwarcie",) + ("przenies x",) * 20)
def cel_odchodzi(i, stan):
    if i == 1: s.stwory[0]["x"] = 105
s.po_kroku = cel_odchodzi
licz_ticki36(b, s, 30)
prz = [e for e in ev if e[0] == "loot_w_walce_przerwany"]
sprawdz("36k cel odszedł daleko (5 pól): przerwanie (cel_daleko lub przerwa_w_krokach), brak zawieszonego lootu",
        prz and prz[0][1]["powod"] == "cel_daleko" and b.lww is None, (prz, b.lww, b.zwloki_czekajace))
# 36k2. LOOT_DYNAMICZNY=1: okno otwarte, cel odszedł na 4 pola: loot nie jest przerywany "cel_daleko"
s, b, wyw, ev, zam = swiat36(kroki=("otwarcie",) + ("przenies x",) * 20)
def cel_odchodzi4(i, stan):
    if i == 1: s.stwory[0]["x"] = 104
s.po_kroku = cel_odchodzi4
licz_ticki36(b, s, 30)
prz = [e for e in ev if e[0] == "loot_w_walce_przerwany"]
sprawdz("36k2 okno otwarte, cel w odl 4: brak przerwania 'cel_daleko'",
        not any(e[1]["powod"] == "cel_daleko" for e in prz), prz)
# 36l. cel odchodzi (uciekający): okno zwłok NIE jest zamykane kliknięciem (pilne), nic nie opóźnia pościgu
sprawdz("36l cel_daleko: bez zamykania okna zwłok (zam pusty)", zam == [], zam)
# 36m. opóźnienie reakcji ("zauważanie") nie dotyczy uciekającego celu dalej niż obok; zdrowego celu dalej: nadal jest
def pauzy_pierwszego_ticka(hp_mob):
    s_ = Swiat(hp=100); s_.zabija = False
    s_.stwory = [{"id": 40, "nazwa": "Rat", "gracz": False, "x": 104, "y": 100, "z": 7, "hp": hp_mob}]
    b_ = zrob(s_, trasa(), okrazenia=1)
    wyw_ = []
    oryg = b_.pauza
    b_.pauza = lambda a=0.1, c=0.3: wyw_.append((a, c)) or oryg(a, c)
    stara = cavebot.REAKCJA
    cavebot.REAKCJA = (5.0, 5.0)          # zegar atrapy płynie z każdym RPC: reakcja musi trwać dłużej niż tick
    try:
        b_.tick()
    finally:
        cavebot.REAKCJA = stara
    return wyw_
sprawdz("36m1 uciekający (HP 20%) odl 4: brak pauzy 'zauważania' (0.05, 0.12)", (0.05, 0.12) not in pauzy_pierwszego_ticka(20),
        pauzy_pierwszego_ticka(20))
sprawdz("36m2 zdrowy (HP 100%) odl 4: pauza 'zauważania' zostaje (imitacja człowieka)", (0.05, 0.12) in pauzy_pierwszego_ticka(100),
        pauzy_pierwszego_ticka(100))
cavebot.ATAK_TYLKO_PRZY_CELU = False

# W1. zamrożenie 11.10 15:44: HP 45% (próg ucieczki + margines lootu), zwłoki odłożone, brak mobów: loot przerywany w kółko.
# W1a. HP w marginesie (45%, próg 40), brak mobów: loot NIE jest przerywany, zwłoki zebrane
s = Swiat(poz=(100,100,7), hp=45); s.zabija = False
b = zrob(s, trasa(), okrazenia=1)
b.zwloki_czekajace = [((101,100,7), s.t)]
w = b.zbierz_loot((101,100,7))
sprawdz("W1a HP 45% (próg 40), brak mobów: loot zebrany, nie przerwany", w == "ok" and b.lootlog == [(101,100,7)] and b.zwloki_chlod == {},
        f"w={w} loot={b.lootlog}")
# W1b. HP w marginesie + żywy mob w promieniu 6: przerwanie lootu
s = Swiat(poz=(100,100,7), hp=45); s.zabija = False
s.stwory = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 104, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1)
w = b.zbierz_loot((101,100,7))
sprawdz("W1b HP 45% + mob 4 pola: loot przerwany, zwłoki odłożone z chłodzeniem",
        w == "przerwany" and b.lootlog == [] and any(z == (101,100,7) for z, _ in b.zwloki_czekajace)
        and b.zwloki_chlod.get((101,100,7), 0) > s.t, f"w={w} chlod={b.zwloki_chlod}")
# W1b2. HP w marginesie, mob dalej niż 6 pól: loot trwa
s = Swiat(poz=(100,100,7), hp=45); s.zabija = False
s.stwory = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 107, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1)
w = b.zbierz_loot((101,100,7))
sprawdz("W1b2 HP 45% + mob 7 pól: loot nie przerwany", w == "ok" and b.lootlog == [(101,100,7)], f"w={w}")
# W1c. HP realnie przy progu (<= próg + 3): przerwanie nawet bez mobów
s = Swiat(poz=(100,100,7), hp=42); s.zabija = False
b = zrob(s, trasa(), okrazenia=1)
w = b.zbierz_loot((101,100,7))
sprawdz("W1c HP 42% (próg 40), brak mobów: loot przerwany", w == "przerwany" and b.lootlog == [], f"w={w}")
# W1d. po takim przerwaniu bot rusza trasą w < 10 s (nie kręci się w miejscu), zwłoki wracają dopiero po chłodzeniu
s = Swiat(poz=(100,100,7), hp=43); s.zabija = False
b = zrob(s, trasa(), okrazenia=1)
b.zwloki_czekajace = [((101,100,7), s.t)]
t0 = s.t; start = tuple(s.poz); ruszyl = None
for i in range(40):
    b.tick()
    if tuple(s.poz) != start and ruszyl is None:
        ruszyl = s.t - t0
        break
sprawdz("W1d HP 43%, zwłoki odłożone, brak mobów: bot rusza trasą w < 10 s", ruszyl is not None and ruszyl < 10, f"ruszyl={ruszyl}")
przerw = [l for l in cavelog if "Przerywam loot: niskie HP" in l]
# W1e. spam logu: wiele przerwań w krótkim czasie = jedna linia
s = Swiat(poz=(100,100,7), hp=42); s.zabija = False
b = zrob(s, trasa(), okrazenia=1)
n0 = len([l for l in cavelog if "Przerywam loot: niskie HP" in l])
for _ in range(6):
    b.zbierz_loot((101,100,7))
n1 = len([l for l in cavelog if "Przerywam loot: niskie HP" in l])
sprawdz("W1e log 'Przerywam loot: niskie HP' maks. raz na 5 s", n1 - n0 == 1, f"n={n1-n0}")
# W1f. watchdog: bezczynność 25 s, zwłoki odłożone, brak mobów, HP 100: porzuca zwłoki, idzie trasą
def swiat_wd(hp=100, stwory=None):
    s_ = Swiat(poz=(100,100,7), hp=hp); s_.zabija = False
    s_.stwory = stwory or []
    b_ = zrob(s_, trasa(), okrazenia=1)
    b_.ruch_poz = (100,100,7); b_.ruch_czas = s_.t - 25; b_.aktywnosc_ts = s_.t - 25
    b_.zwloki_czekajace = [((101,100,7), s_.t - 25)]   # zwłoki stare (zabite 25 s temu): watchdog może je porzucić
    b_.zwloki_wiek = {(101,100,7): s_.t - 25}
    s_.t += 1
    return s_, b_
def wd_log(): return [l for l in cavelog if l.startswith("Watchdog: bezczynność")]
cavelog_n = len(wd_log())
s, b = swiat_wd()
tele = []
b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: tele.append((typ, d)), probka=lambda *a: None)
b._tele_tick = lambda *a, **k: None
b.tick()
sprawdz("W1f watchdog: log + telemetria watchdog_bezczynnosc, zwłoki wyczyszczone, chłodzenie lootu 30 s, loot nie wywołany",
        len(wd_log()) == cavelog_n + 1 and [t for t, _ in tele] == ["watchdog_bezczynnosc"] and b.zwloki_czekajace == []
        and b.loot_chlod_do >= s.t - 5 + 25 and b.lootlog == [], f"tele={tele} chlod={b.loot_chlod_do} loot={b.lootlog}")
# W1g. limit 1 na 60 s
b.ruch_czas = s.t - 25; b.aktywnosc_ts = s.t - 25; b.zwloki_czekajace = [((101,100,7), s.t - 25)]
b.tick()
sprawdz("W1g watchdog nie odpala drugi raz w ciągu 60 s", len(wd_log()) == cavelog_n + 1, len(wd_log()) - cavelog_n)
# W1h. nie odpala: żywy mob w promieniu 8 (walka)
s, b = swiat_wd(stwory=[{"id": 9, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 7, "hp": 100}])
n = len(wd_log()); b.tick()
sprawdz("W1h watchdog nie odpala przy żywym mobie w promieniu 8", len(wd_log()) == n)
# W1i. nie odpala: pauza mózgu / rozmowa
s, b = swiat_wd(); b.wstrzymany_do = s.t + 100
n = len(wd_log()); b.tick()
sprawdz("W1i watchdog nie odpala przy pauzie (wstrzymany_do)", len(wd_log()) == n)
s, b = swiat_wd(); b.rozmowa_do = s.t + 100
n = len(wd_log()); b.tick()
sprawdz("W1i2 watchdog nie odpala w rozmowie", len(wd_log()) == n)
# W1j. nie odpala: wypad (flaga/stan), HP przy progu
s, b = swiat_wd(); b.wypad_aktywny = True
n = len(wd_log()); b.tick()
sprawdz("W1j watchdog nie odpala w wypadzie", len(wd_log()) == n)
s, b = swiat_wd(hp=42)
n = len(wd_log()); b.tick()
sprawdz("W1k watchdog nie odpala przy HP <= próg + 3", len(wd_log()) == n)
# W1l. nie odpala bez bezczynności (pozycja zmieniona niedawno)
s, b = swiat_wd(); b.ruch_czas = s.t - 5
n = len(wd_log()); b.tick()
sprawdz("W1l watchdog nie odpala po 5 s postoju", len(wd_log()) == n)
# W1m. walka 25 s w miejscu (pozycja stoi), zgon celu, 2 świeże zwłoki: watchdog NIE odpala, zwłoki do lootu
_lk0 = cavebot.ATAK_LIMIT_KLIKOW; cavebot.ATAK_LIMIT_KLIKOW = 0   # 13.10 P1a: po limicie klików cel jest twardo ignorowany (dawniej wybierany od razu znów)
s = Swiat(poz=(100,100,7)); s.zabija = False
s.stwory = [{"id": 5, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}]
b = zrob(s, trasa(), okrazenia=1)
b.ruch_poz = (100,100,7); b.ruch_czas = s.t
b._tele_tick = lambda *a, **k: None
n = len(wd_log())
for _ in range(400):
    if s.t >= 25: break
    b.tick()
t_walki = s.t
s.stwory[:] = []                       # cel zginął
b.odloz_zwloki((101,100,7), nowe=True); b.odloz_zwloki((102,100,7), nowe=True)
b.cel = {"id": 5, "nazwa": "Rat", "poz": (101,100,7), "hp": 0, "odl": 1}
b.tick(); b.tick()
sprawdz("W1m 25 s walki w miejscu + zgon celu: watchdog nie odpala, zwłoki nie skasowane/zebrane",
        len(wd_log()) == n and t_walki >= 25 and (len(b.lootlog) > 0 or len(b.zwloki_czekajace) == 2),
        f"t={t_walki:.0f} wd={len(wd_log())-n} loot={b.lootlog} czek={b.zwloki_czekajace}")
cavebot.ATAK_LIMIT_KLIKOW = _lk0
# W1m2. bezpośrednio: ruch dawno, ale aktywność (walka) 2 s temu -> nie odpala
s, b = swiat_wd(); b.aktywnosc_ts = s.t - 2
n = len(wd_log()); b.tick()
sprawdz("W1m2 aktywnosc_ts 2 s temu (stary ruch_czas): watchdog nie odpala", len(wd_log()) == n)
# W1n. oryginalne zamrożenie: brak aktywności 25 s -> odpala, N = czas od ostatniej aktywności w logu
s, b = swiat_wd(); b.aktywnosc_ts = s.t - 25
n = len(wd_log()); b.tick()
sprawdz("W1n zamrożenie bez aktywności 25 s: watchdog odpala, zwłoki wyczyszczone",
        len(wd_log()) == n + 1 and b.zwloki_czekajace == [], f"wd={wd_log()[-1:]}")
# W1o. watchdog nie kasuje zwłok młodszych niż 20 s od zabicia (stare porzuca)
s, b = swiat_wd(); b.aktywnosc_ts = s.t - 25
b.zwloki_czekajace = [((101,100,7), s.t - 40), ((102,100,7), s.t - 5)]
b.zwloki_wiek = {(101,100,7): s.t - 40, (102,100,7): s.t - 5}
n = len(wd_log()); b.tick()
sprawdz("W1o watchdog zostawia zwłoki młodsze niż 20 s, porzuca stare",
        len(wd_log()) == n + 1 and (101,100,7) not in [z for z, _ in b.zwloki_czekajace]
        and ((102,100,7) in [z for z, _ in b.zwloki_czekajace] or (102,100,7) in b.lootlog) and (101,100,7) not in b.lootlog
        and b.loot_chlod_do < s.t + 5, f"czek={b.zwloki_czekajace} loot={b.lootlog} chlod={b.loot_chlod_do}")

# L2. loot w walce i odłożone zwłoki (12.10): próg HP względem ucieczki, TTL od zabicia, ucieczka nie pali TTL,
# zwłoki przed pościgiem, pauza po przerwaniu i respektowanie pauzy mózgu.
import pokretla as _pok
def swiat_l2(hp=100, mob=None, zwloki=((101, 100, 7),), zbierz=None):
    s_ = Swiat(poz=(100, 100, 7), hp=hp); s_.zabija = False
    s_.stwory = [] if mob is None else [dict({"id": 90, "nazwa": "Rat", "gracz": False, "z": 7, "hp": 100}, x=mob[0], y=mob[1],
                                              **({"hp": mob[2]} if len(mob) > 2 else {}))]
    b_ = zrob(s_, trasa(), okrazenia=1)
    b_.tele = None
    b_.prog_aktualny = 40.0
    b_.zwloki_czekajace = [(tuple(z), s_.t) for z in zwloki]
    b_.zwloki_wiek = {tuple(z): s_.t for z in zwloki}
    if zbierz is not None:
        b_.loot.zbierz = zbierz
    return s_, b_
# L2a. próg HP loota w walce = prog_aktualny + 15 (wcześniej stałe 70)
s, b = swiat_l2()
cel_ = {"x": 101, "y": 100, "z": 7, "atakowany": True, "nazwa": "Rat", "id": 90}
b.hp_gracza_spadek = float("-inf"); b.hp_wzrost = s.t
sprawdz("L2a HP 56% przy progu 40: loot w walce dozwolony (> próg + 15)",
        b._lww_powod(cel_, {"proc": 56.0, "hp": 56, "max_hp": 100}, (100, 100, 7), [], s.t) is None)
sprawdz("L2a2 HP 55% przy progu 40: 'hp' (<= próg + 15)",
        b._lww_powod(cel_, {"proc": 55.0, "hp": 55, "max_hp": 100}, (100, 100, 7), [], s.t) == "hp")
cavebot.LOOT_W_WALCE_HP = 80
sprawdz("L2a3 stała LOOT_W_WALCE_HP=80 nadal działa jako twarda dolna granica",
        b._lww_powod(cel_, {"proc": 70.0, "hp": 70, "max_hp": 100}, (100, 100, 7), [], s.t) == "hp")
cavebot.LOOT_W_WALCE_HP = 0
ok_, bl_ = _pok.waliduj({"LOOT_W_WALCE_HP_MARGINES": 10}, {"LOOT_W_WALCE_HP_MARGINES": 15})
sprawdz("L2a4 pokrętło marginesu: obniżenie odrzucone (analityk tylko zaostrza)", ok_ == {} and bl_, (ok_, bl_))
ok_, bl_ = _pok.waliduj({"LOOT_W_WALCE_HP_MARGINES": 25, "LOOT_W_WALCE_HP": 50}, {"LOOT_W_WALCE_HP_MARGINES": 15, "LOOT_W_WALCE_HP": 0})
sprawdz("L2a5 pokrętło marginesu i progu bezwzględnego: zaostrzenie dozwolone", len(ok_) == 2 and not bl_, (ok_, bl_))
# L2b. TTL liczony od zabicia, dalekie zwłoki pomijane (nie kasowane), 120 s
s, b = swiat_l2(zwloki=())
b.odloz_zwloki((101, 100, 7), nowe=True)
t0 = s.t; s.t += 50
b.zwloki_czekajace = []; b.odloz_zwloki((101, 100, 7))       # ponowne odłożenie po przerwaniu: bez resetu czasu
sprawdz("L2b ponowne odłożenie nie resetuje TTL (czas zabicia)", b.zwloki_czekajace == [((101, 100, 7), t0)], b.zwloki_czekajace)
b.zwloki_czekajace = [((111, 100, 7), s.t), ((115, 100, 7), s.t)]   # odl 11 (w zasięgu 12) i 15 (poza)
zw = b.zwloki_do_zebrania((100, 100, 7))
sprawdz("L2b2 zasięg 12: zwłoki w odl 11 wybrane, dalsze (15) zostają na liście", zw == (111, 100, 7)
        and [z for z, _ in b.zwloki_czekajace] == [(115, 100, 7)], (zw, b.zwloki_czekajace))
zw = b.zwloki_do_zebrania((100, 100, 7))
sprawdz("L2b3 za daleko: None, wpis zostaje (nie skasowany)", zw is None and len(b.zwloki_czekajace) == 1, b.zwloki_czekajace)
zw = b.zwloki_do_zebrania((108, 100, 7))
sprawdz("L2b4 po zbliżeniu się zwłoki są znów do zebrania", zw == (115, 100, 7), zw)
b.odloz_zwloki((120, 100, 7), nowe=True); s.t += cavebot.ZWLOKI_WAZNE + 1
b.zwloki_do_zebrania((100, 100, 7))
sprawdz("L2b5 po ZWLOKI_WAZNE (120 s) wpis wygasa", b.zwloki_czekajace == [] and cavebot.ZWLOKI_WAZNE == 120
        and cavebot.ZWLOKI_ZASIEG == 12, b.zwloki_czekajace)
# L2c. ucieczka nie pali TTL + priorytet powrotu po zwłoki przed szukaniem celu
s, b = swiat_l2(hp=100, zwloki=((103, 100, 7),))
b.ucieczka_od = s.t; s.t += 45
b._zwloki_po_ucieczce(s.t)
sprawdz("L2c po ucieczce czasy wpisów dosunięte o czas ucieczki (wiek 0), priorytet włączony",
        b.zwloki_czekajace[0][1] == s.t and b.zwloki_priorytet_do > s.t, (b.zwloki_czekajace, b.zwloki_priorytet_do))
s.stwory = [{"id": 90, "nazwa": "Rat", "gracz": False, "x": 106, "y": 100, "z": 7, "hp": 100}]
b.tick()
sprawdz("L2c2 po ucieczce: najpierw zwłoki (odl 3), potem szukanie celu", b.lootlog == [(103, 100, 7)] and b.cel is None,
        f"loot={b.lootlog} cel={b.cel}")
# L2d. zwłoki w odl 1, mob w odl 5, nic nie styka: zbierz przed pościgiem
s, b = swiat_l2(mob=(105, 100))
b.tick()
sprawdz("L2d zwłoki odl 1, mob odl 5: zebrane przed pościgiem, brak celu", b.lootlog == [(101, 100, 7)] and b.cel is None,
        f"loot={b.lootlog} cel={b.cel}")
s, b = swiat_l2(mob=(105, 100))
cavebot.ZWLOKI_PRZED_CELEM = False
b.tick()
cavebot.ZWLOKI_PRZED_CELEM = True
sprawdz("L2d2 ZWLOKI_PRZED_CELEM=False, LOOT_DYNAMICZNY=1: dynamiczny loot i tak zbiera zwłoki obok", b.lootlog == [(101, 100, 7)] and b.cel is None,
        f"loot={b.lootlog} cel={b.cel}")
s, b = swiat_l2(mob=(105, 100))
cavebot.ZWLOKI_PRZED_CELEM = False; cavebot.LOOT_DYNAMICZNY = 0
b.tick()
cavebot.ZWLOKI_PRZED_CELEM = True; cavebot.LOOT_DYNAMICZNY = 1
sprawdz("L2d2b ZWLOKI_PRZED_CELEM=False, LOOT_DYNAMICZNY=0: dawne zachowanie (cel wybrany, loot po walce)", b.lootlog == [] and b.cel is not None,
        f"loot={b.lootlog} cel={b.cel}")
s, b = swiat_l2(mob=(103, 100, 10))     # uciekający (HP 10%) w odl 3
b.tick()
sprawdz("L2d3 uciekający cel w odl <= 4: pościg przed zwłokami", b.lootlog == [] and b.cel is not None, f"loot={b.lootlog} cel={b.cel}")
s, b = swiat_l2(mob=(102, 101))         # mob w odl 2: walka pierwsza
b.tick()
sprawdz("L2d4 LOOT_DYNAMICZNY=1: mob w odl 2, zwłoki obok: zebrane przed walką", b.lootlog == [(101, 100, 7)] and b.cel is None, f"loot={b.lootlog} cel={b.cel}")
s, b = swiat_l2(mob=(102, 101))
cavebot.LOOT_DYNAMICZNY = 0
b.tick()
cavebot.LOOT_DYNAMICZNY = 1
sprawdz("L2d4b LOOT_DYNAMICZNY=0: mob w odl 2: walka przed zwłokami", b.lootlog == [] and b.cel is not None, f"loot={b.lootlog} cel={b.cel}")
s, b = swiat_l2(hp=45, mob=(105, 100))  # HP <= próg + 15
b.tick()
sprawdz("L2d5 HP 45% (próg 40): nie zbieramy przed celem", b.lootlog == [], f"loot={b.lootlog}")
# L2e. po przerwanym zbieraniu pauza (tick nie kręci się bez przerwy), chłodzenie, brak pętli
wolane = []
def zbierz_przerwany(zw_, g_):
    wolane.append(zw_); return "przerwany"
s, b = swiat_l2(mob=(105, 100), zbierz=zbierz_przerwany)
b.odloz_zwloki_orig = b.odloz_zwloki
def zbierz_i_odloz(zw_, g_):
    wolane.append(zw_); b.odloz_zwloki(zw_); return "przerwany"
b.loot.zbierz = zbierz_i_odloz
t0 = s.t; b.tick()
sprawdz("L2e przerwany loot przed celem: pauza >= 0,3 s w ticku, zwłoki wracają na listę z chłodzeniem",
        s.t - t0 >= 0.3 and len(wolane) == 1 and b.zwloki_chlod.get((101, 100, 7), 0) > s.t - 0.7
        and len(b.zwloki_czekajace) == 1, (s.t - t0, wolane, b.zwloki_chlod))
# L2f. blok zwykłych odłożonych (bez mobów): przerwany = pauza; pauza mózgu = nie zbieramy
wolane.clear()
s, b = swiat_l2(zwloki=((103, 100, 7),))
b.loot.zbierz = lambda zw_, g_: (wolane.append(zw_), b.odloz_zwloki(zw_), "przerwany")[-1]
t0 = s.t; b.tick()
sprawdz("L2f przerwany loot odłożonych (bez celu): pauza po przerwaniu", len(wolane) == 1 and s.t - t0 >= 0.3, (len(wolane), s.t - t0))
wolane.clear()
s, b = swiat_l2(zwloki=((103, 100, 7),))
b.loot.zbierz = lambda zw_, g_: (wolane.append(zw_), "ok")[-1]
b._poscig_przerwanie = lambda: "wstrzymanie"
b.tick()
sprawdz("L2f2 pauza mózgu (wstrzymanie): loot odłożonych nie startuje, zwłoki zostają", wolane == [] and len(b.zwloki_czekajace) == 1,
        (wolane, b.zwloki_czekajace))
# L2h. zaległe okno zwłok (pilne przerwanie lootu w walce): zamykane przy najbliższej spokojnej okazji
zam_ = []
s, b = swiat_l2(zwloki=())
b.lww_zalegle = {"stan": {"faza": "plan", "klucz": (2, 3994)}, "t": s.t, "proby": 0}
b.loot.zamknij_w_walce = lambda stan, log=print, swiezo=False: zam_.append(swiezo) or True
b.tick()
sprawdz("L2h zaległe okno zwłok zamknięte (świeży plan) przy braku celu i mobów", zam_ == [True] and b.lww_zalegle is None, (zam_, b.lww_zalegle))
s, b = swiat_l2(zwloki=(), mob=(101, 100))
b.lww_zalegle = {"stan": {"faza": "plan", "klucz": (2, 3994)}, "t": s.t, "proby": 0}
zam_.clear(); b.loot.zamknij_w_walce = lambda stan, log=print, swiezo=False: zam_.append(swiezo) or True
b.tick()
sprawdz("L2h2 mob obok: zaległego okna nie zamykamy w trakcie walki", zam_ == [] and b.lww_zalegle is not None, zam_)
# L2i. zwykły loot nie gubi zaległego okna zwłok (innych zwłok niż te, które otwiera): zostaje do zamknięcia,
#      limit czasu liczony od końca lootu
s, b = swiat_l2(zwloki=((103, 100, 7),))
b.lww_zalegle = {"stan": {"faza": "przenies", "klucz": (0, 3994)}, "t": s.t - 15, "proby": 2}
b.loot.zbierz = lambda zw_, g_=None: "ok"
b.zbierz_loot((103, 100, 7))
sprawdz("L2i zwykły loot: zaległe okno zostaje na liście, czas i próby liczone od końca lootu",
        b.lww_zalegle is not None and b.lww_zalegle["t"] == s.t and b.lww_zalegle["proby"] == 0, b.lww_zalegle)
# L2g. telemetria: próbka niesie flagę ataku i powód lootu w walce
import telemetria as _tel, tempfile as _tf
with _tf.TemporaryDirectory() as d_:
    tel = _tel.Telemetria(katalog=_tf.gettempdir() if False else __import__("pathlib").Path(d_), zegar=lambda: s.t, zapis=False)
    s, b = swiat_l2()
    b._lww_diag("hp", False)
    r = tel.probka(b, {"proc": 100.0}, (100, 100, 7), [])
    sprawdz("L2g próbka telemetrii: lww_powod i atak", r.get("lww_powod") == "hp" and r.get("atak") is False, r)

# 37. wypad po pochodnie / jedzenie (wypad.py): prawdziwa mapa, symulator z piętrami (lina w górę, dziura w dół), NPC na czacie
if _mapa_mod.PLIK_MAPY.is_file():
    import json as _json37, re as _re37, tempfile as _tmp37
    from pathlib import Path as _P37
    import wypad as _wy
    import pokretla as _pok37
    _DO = [tuple(p) for p in _json37.loads((cavebot.KATALOG_TRAS / "do_miasta.json").read_text())]
    _Z = [tuple(p) for p in _json37.loads((cavebot.KATALOG_TRAS / "z_miasta.json").read_text())]
    SKLEP37 = (32061, 32180, 7)
    _stare_wypad = {k: getattr(cavebot, k) for k in ("WYPAD_SPRAWDZ_S", "WYPAD_JEDZENIE_SPOKOJ_S")}
    cavebot.WYPAD_SPRAWDZ_S = 2.0; cavebot.WYPAD_JEDZENIE_SPOKOJ_S = 3.0

    # 37a. plan z prawdziwych tras: cztery liny w górę, cztery dziury w dół (z7 -> z8 bez flagi), przejścia sąsiadują z polami
    etapy_do, etapy_z = _wy.wczytaj_plan(mapa=PRAWDZIWA)
    typy_do = [e["typ"] for e in etapy_do if e["typ"] != "IDZ"]
    typy_z = [e["typ"] for e in etapy_z if e["typ"] != "IDZ"]
    liny = [e for e in etapy_do if e["typ"] == "LINA"]
    dz = [e for e in etapy_z if e["typ"] == "DZIURA"]
    sprawdz("37a plan do_miasta: 4 liny w górę z11->10->9->8->7, bez błędów geometrii",
            typy_do == ["LINA"] * 4 and [e["ladunek"][2] for e in liny] == [10, 9, 8, 7]
            and [e["cel"] for e in liny] == [(32050,32155,11), (32050,32159,10), (32059,32171,9), (32060,32173,8)]
            and not _wy.sprawdz_plan(etapy_do), f"{typy_do} {[e['cel'] for e in liny]} {_wy.sprawdz_plan(etapy_do)}")
    sprawdz("37a' plan z_miasta: brakujący początek odtworzony (z7 -> z8 przez (32060,32173,7)), 4 dziury w dół",
            typy_z == ["DZIURA"] * 4 and [e["ladunek"][2] for e in dz] == [8, 9, 10, 11]
            and dz[0]["dziura"] == (32060,32173,7) and not dz[0]["pewna"] and all(e["pewna"] for e in dz[1:])
            and etapy_z[0]["punkty"][0] == SKLEP37 and etapy_z[-1]["punkty"][-1] == (32050,32155,11)
            and not _wy.sprawdz_plan(etapy_z), f"{typy_z} {[(e['dziura'], e['pewna']) for e in dz]}")

    class Swiat37(Swiat):
        """Świat z piętrami na prawdziwej mapie: strzałka/klik po polach z mapy, dziury (krok) i liny (Use),
        NPC Al Dee na czacie, plecak z pochodniami/jedzeniem, slot pochodni."""
        def __init__(s, poz, **kw):
            Swiat.__init__(s, poz=poz, **kw)
            s.dziury_krok, s.uzyj_pola, s.liny = {}, {}, {}
            for e in etapy_do + etapy_z:
                if e["typ"] == "LINA": s.liny[e["cel"]] = e["ladunek"]
                elif e["typ"] == "DZIURA":
                    (s.dziury_krok if e["pewna"] else s.uzyj_pola)[e["dziura"]] = e["ladunek"]
            s.kliki = []; s.klik_cel = None; s.pietra = [poz[2]]
            s.slot = 2925
            s.plecak = {3003: 1, 3031: 120}
            s.plecak_widoczny = True
            s.msgs = []; s.mowa = []; s.rope_wywolania = 0; s.rope_psuje = 0; s.rope_dziala = True
            s.drab_wywolania = 0; s.drab_licz = {}; s.drab_psuje = 0; s.drab_tryb = 'cel'; s.drab_pola = []
            s.npc_odpowiada = True; s.sprzedaje = {"torch": True, "ham": True}; s.zloto = 1000; s.oczek = None
            s.uzyj_dziala = True; s.grate_krok = False
        def zajete(s):
            return {(m["x"], m["y"]) for m in s.stwory if m.get("hp", 100) > 0 and m.get("z", s.poz[2]) == s.poz[2]}
        def zmiana(s):
            if s.pietra[-1] != s.poz[2]: s.pietra.append(s.poz[2])
        def npc_say(s, t): s.msgs.append({"autor": "Al Dee", "tekst": t, "kanal": "Default", "czas": "", "nr": None})
        def czat(s, t):
            s.mowa.append(t); s.msgs.append({"autor": "Ja", "tekst": t, "kanal": "Default", "czas": "", "nr": None})
            if not (s.poz[2] == 7 and max(abs(s.poz[0]-SKLEP37[0]), abs(s.poz[1]-SKLEP37[1])) <= 3 and s.npc_odpowiada):
                return
            l = t.lower()
            m = _re37.match(r"buy (\d+) (\w+)$", l)
            if l == "hi":
                s.npc_say("Hello, hello, Ja! Please come in, look, and buy!")
            elif m:
                n, nazwa = int(m[1]), m[2]
                if not s.sprzedaje.get(nazwa): s.npc_say("Sorry, I do not sell that.")
                elif s.zloto < 2 * n: s.npc_say("You do not have enough gold.")
                else:
                    s.oczek = (nazwa, n)
                    s.npc_say(f"Do you want to buy {n} {nazwa}s for {2 * n} gold coins?")
            elif l == "yes" and s.oczek:
                nazwa, n = s.oczek; s.oczek = None; s.zloto -= 2 * n
                ident = 2920 if nazwa == "torch" else 3582
                s.plecak[ident] = s.plecak.get(ident, 0) + n
                s.npc_say("Thank you.")
    class Ops37:
        id_przedmiotow = {"torch": {2920}, "ham": {3582}}
        id_jedzenia = {3582, 3577, 3607}
        def __init__(o, s): o.s = s
        def ekwipunek(o): return {10: o.s.slot} if o.s.slot is not None else {}
        def plecak(o): return {"id": dict(o.s.plecak)} if o.s.plecak_widoczny else None
        def wiadomosci(o):
            w, o.s.msgs[:] = list(o.s.msgs), []
            return w
        def czat(o, t): o.s.czat(t)
        def uzyj_line(o, cel, poz):
            s = o.s; s.rope_wywolania += 1; s.t += 0.5
            if s.rope_dziala and s.rope_wywolania > s.rope_psuje and cel in s.liny \
                    and max(abs(s.poz[0]-cel[0]), abs(s.poz[1]-cel[1])) <= 1 and s.poz[2] == cel[2]:
                s.poz[:] = list(s.liny[cel]); s.klik_cel = None
        def uzyj_pole(o, pole, poz):
            s = o.s; s.t += 0.5
            # drabina (przejście w górę): Ctrl+klik; tryb 'cel' = działa klik w pole drabiny, 'wlasne' = tylko w pole własne
            dr = [c for c in s.liny if c[2] == s.poz[2] and max(abs(s.poz[0]-c[0]), abs(s.poz[1]-c[1])) <= 1]
            if dr:
                c = dr[0]; s.drab_wywolania += 1; s.drab_pola.append(tuple(pole)); s.drab_licz[c] = s.drab_licz.get(c, 0) + (tuple(pole) == c)
                trafia = (tuple(pole) == c) if s.drab_tryb == 'cel' else (
                    (tuple(pole[:2]) == tuple(s.poz[:2])) if s.drab_tryb == 'wlasne' else False)
                if trafia and s.drab_licz[c] > s.drab_psuje:   # psuje = tyle pierwszych klików W POLE drabiny, na każdej drabinie, bez efektu
                    s.poz[:] = list(s.liny[c]); s.klik_cel = None
                return
            if s.uzyj_dziala and tuple(pole) in s.uzyj_pola and max(abs(s.poz[0]-pole[0]), abs(s.poz[1]-pole[1])) <= 1:
                s.poz[:] = list(s.uzyj_pola[tuple(pole)]); s.klik_cel = None
    def wolne37(x, y, z):
        fl = PRAWDZIWA.flagi(x, y, z)
        return bool(fl) and not (fl & 4) and not (fl & 2)
    def zrob37(s, **kw):
        b = zrob_klik(s, KANALY, mapa=PRAWDZIWA, czas_s=10 ** 6, **kw)
        def krok(k):
            d = bot.KIERUNKI[k]; s.t += 0.2
            n = (s.poz[0] + d[0], s.poz[1] + d[1], s.poz[2])
            if n in s.dziury_krok or (s.grate_krok and n in s.uzyj_pola):
                s.poz[:] = list((s.dziury_krok.get(n) or s.uzyj_pola[n])); s.klik_cel = None; s.zmiana()
                return tuple(s.poz)
            if not wolne37(*n) or (n[0], n[1]) in s.zajete(): return None
            s.poz[:] = list(n); return tuple(s.poz)
        b.postac.krok = krok
        def klawisz(k):
            s.klawisze.append(k)
            if k in bot.KIERUNKI: s.klik_cel = None; krok(k); s.t -= 0.2
        b.postac.klawisz = klawisz
        def klik(dx, dy): s.kliki.append((dx, dy)); s.klik_cel = (s.poz[0] + dx, s.poz[1] + dy)
        def spij(d):
            s.t += d
            if s.klik_cel and d >= 0.08 and tuple(s.poz[:2]) != s.klik_cel:
                dr = PRAWDZIWA.droga(tuple(s.poz), s.klik_cel, list(s.zajete()), dlugosc=0, skosy=False)
                if dr: s.poz[0], s.poz[1] = dr[0][0], dr[0][1]
        b.klik, b.spij = klik, spij
        s.zdarzenia = []
        b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: s.zdarzenia.append((typ, d)), probka=lambda *a: None)
        b._tele_tick = lambda *a, **k: None
        s.ops = Ops37(s)
        s.ops_czat = s.ops.czat
        b.wyprawa = _wy.Wypad(b, s.ops, konf=cavebot, log=cavebot.log)
        # start: najbliższy punkt trasy łowiska
        z = s.poz[2]
        b.idx = min(range(len(KANALY)), key=lambda i: (KANALY[i][2] != z, abs(KANALY[i][0]-s.poz[0]) + abs(KANALY[i][1]-s.poz[1])))
        return b
    def start37():
        # punkt trasy łowiska kanaly2 najbliższy 12. punktowi do_miasta (te trasy się nakładają)
        p = min((q for q in KANALY if q[2] == 11), key=lambda q: abs(q[0]-_DO[12][0]) + abs(q[1]-_DO[12][1]))
        return p
    def bieg37(b, s, maks=6000, fn=None):
        """Tick po ticku do końca wypadu (albo maks). Zwraca (liczba ticków, czy wypad wystartował)."""
        wystartowal = False
        for i in range(maks):
            if fn: fn(i)
            b.tick(); s.zmiana()
            if b.wyprawa.aktywny: wystartowal = True
            elif wystartowal: return i, True
        return maks, wystartowal
    def ev(s, typ): return [d for t, d in s.zdarzenia if t == typ]

    # 37b. wyzwalacz A (pochodnie): tabela warunków (bez ruszania; _okazja wołane ręcznie)
    def okazja_po(s, b, n=3):
        wynik = False
        for _ in range(n):
            s.t += 20
            b.ruch_poz = tuple(s.poz); b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
            wynik = b.wyprawa._okazja(s.t)
            if wynik: break
        return wynik
    def swiat_b(slot=2925, plecak=None, hp=100, widoczny=True, moby=None):
        s = Swiat37(start37(), hp=hp)
        s.slot = slot; s.plecak_widoczny = widoczny
        if plecak is not None: s.plecak = plecak
        s.stwory = moby or []
        b = zrob37(s)
        return s, b
    s, b = swiat_b()
    sprawdz("37b ostatnia pochodnia (2925), zapas 0, HP 100: start po 2 potwierdzeniach, powód pochodnie",
            okazja_po(s, b) and b.wyprawa.powod == "pochodnie" and b.wypad_aktywny, f"powod={b.wyprawa.powod}")
    s, b = swiat_b()
    sprawdz("37b' pierwszy odczyt nie startuje (debounce)", not okazja_po(s, b, 1) and not b.wypad_aktywny)
    for opis, kw in (("zapas 1 pochodnia", dict(plecak={3003: 1, 2920: 1})),
                     ("pochodnia w slocie jeszcze 2923", dict(slot=2923)),
                     ("HP 60% (< 70)", dict(hp=60)),
                     ("plecak nieotwarty", dict(widoczny=False)),
                     ("żywy Rat w promieniu 8", dict(moby=[dict(szczur(60, 0, y=0), x=start37()[0] + 3, y=start37()[1], z=11)]))):
        s, b = swiat_b(**kw)
        sprawdz(f"37b'' brak startu: {opis}", not okazja_po(s, b, 4) and not b.wypad_aktywny)
    s, b = swiat_b(slot=None)
    sprawdz("37b''' pusty slot + zapas 0 = start", okazja_po(s, b) and b.wyprawa.powod == "pochodnie")
    s, b = swiat_b(); b.wyprawa.zablokowany = True
    sprawdz("37b4 po STOP/ALARM_GM (zablokowany) nie startuje samo", not okazja_po(s, b, 4))
    # wyzwalacz B (jedzenie): HP < 50, powyżej progu ucieczki, brak jedzenia, spokój >= 3 s (test) 
    s, b = swiat_b(hp=45, plecak={3003: 1, 2920: 3, 3031: 5}, slot=2923)
    b.wyprawa.spokoj_od = s.t - 100
    sprawdz("37c wyzwalacz jedzenia: brak jedzenia, HP 45%, spokój -> start (powód jedzenie), pochodnia 2923 nie ma znaczenia",
            okazja_po(s, b) and b.wyprawa.powod == "jedzenie", f"powod={b.wyprawa.powod}")
    s, b = swiat_b(hp=45, plecak={3003: 1, 2920: 3, 3582: 4}, slot=2923); b.wyprawa.spokoj_od = s.t - 100
    sprawdz("37c' jedzenie jest w plecaku -> brak startu", not okazja_po(s, b, 4))
    s, b = swiat_b(hp=60, plecak={3003: 1, 2920: 3}, slot=2923); b.wyprawa.spokoj_od = s.t - 100
    sprawdz("37c'' HP 60% (>= 50) -> brak startu po jedzenie", not okazja_po(s, b, 4))
    s, b = swiat_b(hp=38, plecak={3003: 1, 2920: 3}, slot=2923); b.wyprawa.spokoj_od = s.t - 100
    sprawdz("37c''' HP 38% (pod progiem ucieczki) -> brak startu (najpierw ucieczka)", not okazja_po(s, b, 4))
    s, b = swiat_b(hp=45, plecak={3003: 1, 2920: 3}, slot=2923)
    b.ruch_poz = tuple(s.poz); b.wyprawa.spokoj_od = None
    s.t += 1; b.ostatnie_stwory = []
    r = [b.wyprawa._okazja(s.t + i * 0.1) for i in range(3)]
    sprawdz("37c4 brak spokoju (dopiero zaczął) -> brak startu", not any(r) and b.wyprawa.spokoj_od is not None)
    s, b = swiat_b(hp=45, plecak={3003: 1, 2920: 3}, slot=2923)
    b.jedzenie_nie_do = s.t + 1000
    b.wyprawa.spokoj_od = s.t - 100
    s.plecak_widoczny = False
    sprawdz("37c5 plecak nieotwarty, ale 'brak jedzenia' z próby jedzenia -> start", okazja_po(s, b) and b.wyprawa.powod == "jedzenie")

    # 37d. pełny wypad: trasa do sklepu z czterema linami, dialog hi / buy 5 torch / yes + buy 10 ham / yes, powrót z czterema dziurami
    s = Swiat37(start37()); b = zrob37(s)
    n, wyst = bieg37(b, s)
    e_start, e_kon, e_krok = ev(s, "wypad_start"), ev(s, "wypad_koniec"), ev(s, "wypad_krok")
    sprawdz("37d wypad ruszył sam (ostatnia pochodnia, zapas 0), poszedł do sklepu i wrócił",
            wyst and not b.wypad_aktywny and len(e_start) == 1 and len(e_kon) == 1 and e_kon[0]["wynik"] == "ok",
            f"ticki={n} start={e_start} koniec={e_kon} poz={s.poz} piętra={s.pietra}")
    sprawdz("37d' piętra: 11 -> 10 -> 9 -> 8 -> 7 (sklep) -> 8 -> 9 -> 10 -> 11",
            s.pietra == [11, 10, 9, 8, 7, 8, 9, 10, 11], f"{s.pietra}")
    sprawdz("37d'' dialog (ZMIANA CELOWA 11.10: ham usunięty z WYPAD_ZAKUPY): hi, buy 5 torch, yes (bez nicków, bez ham)",
            s.mowa == ["hi", "buy 5 torch", "yes"], f"{s.mowa}")
    sprawdz("37d''' kupione (ZMIANA CELOWA: bez ham): 5 pochodni w plecaku, brak ham, złoto tylko za pochodnie",
            s.plecak.get(2920) == 5 and s.plecak.get(3582) is None and s.zloto == 1000 - 10,
            f"plecak={s.plecak} złoto={s.zloto}")
    sprawdz("37d4 telemetria (ZMIANA CELOWA: drabina zamiast liny): wypad_start (powód), kroki (drabina x4, dziura x4, zakup x1: ZMIANA CELOWA bez ham), wypad_koniec; brak błędów",
            e_start[0]["powod"] == "pochodnie" and sum(1 for d in e_krok if d.get("rodzaj") == "drabina") == 4
            and s.rope_wywolania == 0 and s.drab_wywolania == 4 and set(s.drab_pola) == set(s.liny)
            and sum(1 for d in e_krok if d.get("rodzaj") == "dziura") == 4
            and sum(1 for d in e_krok if d.get("rodzaj") == "zakup") == 1 and not ev(s, "wypad_blad"),
            f"błędy={ev(s, 'wypad_blad')}")
    sprawdz("37d5 koniec: na piętrze 11 przy trasie łowiska, idx ustawiony, stan nie WYPAD, bot idzie dalej",
            s.poz[2] == 11 and b.idx == 131 and b.stan != "WYPAD", f"poz={s.poz} stan={b.stan} idx={b.idx}")
    x0 = tuple(s.poz); bieg(b, s, 60)
    sprawdz("37d6 po wypadzie normalne polowanie (ruch po trasie, bez ponownego wypadu: pochodnia teraz 5 w plecaku)",
            tuple(s.poz) != x0 and not b.wypad_aktywny and len(ev(s, "wypad_start")) == 1)

    # 37e. Al Dee nie sprzedaje ham: pochodnie kupione, odmowa zalogowana, wypad nie utknął
    # ZMIANA CELOWA 11.10: domyślnie WYPAD_ZAKUPY = tylko torch; mechanizm odmowy ham testujemy z jawnie dodanym ham
    _zak_stare = cavebot.WYPAD_ZAKUPY; cavebot.WYPAD_ZAKUPY = {"torch": 5, "ham": 10}
    s = Swiat37(start37()); s.sprzedaje["ham"] = False; b = zrob37(s)
    bieg37(b, s)
    kon = ev(s, "wypad_koniec"); odm = ev(s, "wypad_zakup_odmowa")
    sprawdz("37e brak ham u NPC: torche kupione = sukces, wypad_zakup_odmowa(ham), wrócił na z11",
            kon and kon[0]["wynik"] == "ok" and s.plecak.get(2920) == 5 and s.plecak.get(3582) is None
            and len(odm) == 1 and odm[0]["przedmiot"] == "ham" and s.poz[2] == 11,
            f"koniec={kon} odmowa={odm} plecak={s.plecak} mowa={s.mowa}")
    # 37e'. NPC milczy na "buy 10 ham" (brak 'Do you want to buy' w ~6 s): jedna próba "hi" ponownie, potem odmowa, bez blokady
    s = Swiat37(start37()); b = zrob37(s)
    stare_czat = s.czat
    def czat_bez_ham(t):
        if t.lower() == "buy 10 ham": s.mowa.append(t); return
        stare_czat(t)
    s.czat = czat_bez_ham
    bieg37(b, s)
    cavebot.WYPAD_ZAKUPY = _zak_stare
    odm = ev(s, "wypad_zakup_odmowa"); kon = ev(s, "wypad_koniec")
    sprawdz("37e' brak odpowiedzi na ham: po ponownym hi odmowa 'brak_odpowiedzi', torche zostają, powrót",
            kon and kon[0]["wynik"] == "ok" and odm and odm[0]["powod"] == "brak_odpowiedzi" and s.plecak.get(2920) == 5
            and s.poz[2] == 11, f"koniec={kon} odm={odm} mowa={s.mowa}")

    # 37f. brak złota: jedna próba, brak pętli, powrót na spot (porażka)
    s = Swiat37(start37()); s.zloto = 3; b = zrob37(s)
    bieg37(b, s)
    odm = ev(s, "wypad_zakup_odmowa"); kon = ev(s, "wypad_koniec")
    sprawdz("37f brak złota: odmowa 'brak_zlota' raz, reszta zakupów pominięta, brak ponawiania w kółko, wrócił na z11",
            len(odm) == 1 and odm[0]["powod"] == "brak_zlota" and s.mowa.count("buy 5 torch") <= 2
            and "buy 10 ham" not in s.mowa and s.poz[2] == 11 and kon and kon[0]["wynik"] != "ok"
            and b.wyprawa.porazki == 1, f"odm={odm} mowa={s.mowa} kon={kon}")

    # 37g. NPC nie odpowiada wcale: ponowienia "hi", potem wracamy "po ciemku" z powiadomieniem
    s = Swiat37(start37()); s.npc_odpowiada = False; b = zrob37(s)
    powiadomienia = []
    import powiadom as _pw37
    stare_pw = _pw37.powiadom
    _pw37.powiadom = lambda *a, **k: powiadomienia.append(a)
    try:
        bieg37(b, s)
    finally:
        _pw37.powiadom = stare_pw
    kon = ev(s, "wypad_koniec")
    sprawdz("37g brak NPC: 3x 'hi', błąd brak_npc, powrót na z11 bez zakupów, porażka + powiadomienie, blokada kolejnego wypadu",
            s.mowa.count("hi") == 3 and kon and kon[0]["wynik"] != "ok" and s.poz[2] == 11 and not s.plecak.get(2920)
            and any(d.get("rodzaj") == "brak_npc" for d in ev(s, "wypad_blad")) and powiadomienia
            and b.wyprawa.blokada_do > s.t, f"mowa={s.mowa} kon={kon} pow={powiadomienia}")
    x0 = len(ev(s, "wypad_start")); bieg(b, s, 40)
    sprawdz("37g' po porażce wypad nie startuje od razu ponownie", len(ev(s, "wypad_start")) == x0)

    # 37h. ucieczka w środku wypadu: HP spada na z10 -> cofanie, potem wypad wznawia się od najbliższego punktu
    s = Swiat37(start37()); b = zrob37(s)
    stan_h = {"uciekl": False, "wznowiony": False}
    def fn_h(i):
        if s.poz[2] == 10 and not stan_h["uciekl"]:
            s.hp = 20; stan_h["uciekl"] = True; stan_h["poz"] = tuple(s.poz); stan_h["t"] = i
        elif stan_h["uciekl"] and not stan_h["wznowiony"] and i - stan_h["t"] > 8:
            s.hp = 90; stan_h["wznowiony"] = True
    n, wyst = bieg37(b, s, fn=fn_h)
    kon = ev(s, "wypad_koniec")
    sprawdz("37h ucieczka w wypadzie (z10): bot uciekał (stan UCIECZKA/alarm), po regeneracji wypad dokończony i wrócił",
            stan_h["wznowiony"] and any("UCIECZKA" in l or "uciekam" in l for l in cavelog[-4000:])
            and kon and kon[0]["wynik"] == "ok" and s.pietra[-1] == 11 and s.plecak.get(2920) == 5,
            f"stan={stan_h} kon={kon} piętra={s.pietra}")

    # 37i. blokada: Rat na korytarzu trasy (walka, loot), potem NIE-cel (Troll, filtr --potwory Rat) stoi na trasie i odchodzi
    s = Swiat37(start37()); b = zrob37(s, potwory=["Rat"])
    p_rat = _DO[16]; p_troll = _DO[20]
    s.stwory = [{"id": 700, "nazwa": "Rat", "gracz": False, "x": p_rat[0], "y": p_rat[1], "z": 11, "hp": 100},
                {"id": 701, "nazwa": "Troll", "gracz": False, "x": p_troll[0], "y": p_troll[1], "z": 11, "hp": 100}]
    def fn_i(i):
        s.stwory[:] = [m for m in s.stwory if m["hp"] > 0]
        for m in s.stwory:
            if m["nazwa"] == "Troll" and s.t > 600: m["hp"] = 0   # troll odchodzi po 10 min symulacji
    n, wyst = bieg37(b, s, fn=fn_i)
    kon = ev(s, "wypad_koniec")
    sprawdz("37i blokady: Rat na trasie zabity (walka), Troll poza filtrem blokuje i odchodzi; wypad dokończony",
            kon and kon[0]["wynik"] == "ok" and len(s.ataki) >= 1 and s.poz[2] == 11, f"kon={kon} ataki={len(s.ataki)} poz={s.poz}")

    # 37j. STOP w środku wypadu: Zatrzymano, wypad zablokowany, żadnych dalszych klawiszy/klików/czatu
    s = Swiat37(start37()); b = zrob37(s)
    bieg37(b, s, maks=400, fn=None) if False else None
    for i in range(3000):
        b.tick(); s.zmiana()
        if s.pietra[-1] == 9: break
    sprawdz("37j wypad w toku (z9, aktywny)", b.wypad_aktywny and b.wyprawa.aktywny, f"piętra={s.pietra}")
    tmp = _P37(_tmp37.mkdtemp())
    stare_stop, stare_env = bot.STOP, _os.environ.pop("RETRONIC_TESTY", None)
    (tmp / "STOP").write_text("")
    bot.STOP = tmp / "STOP"
    n_kl, n_kliki, n_mowa = len(s.klawisze), len(s.kliki), len(s.mowa)
    try:
        try:
            b.tick(); wyj = None
        except bot.Zatrzymano as e:
            wyj = e
    finally:
        bot.STOP = stare_stop
        if stare_env is not None: _os.environ["RETRONIC_TESTY"] = stare_env
    sprawdz("37j STOP (plik) w wypadzie: wyjątek Zatrzymano, zero nowych klawiszy/klików/czatu",
            wyj is not None and (len(s.klawisze), len(s.kliki), len(s.mowa)) == (n_kl, n_kliki, n_mowa),
            f"{wyj} {len(s.klawisze) - n_kl} {len(s.kliki) - n_kliki}")
    s2 = Swiat37(start37()); b2 = zrob37(s2)
    for i in range(3000):
        b2.tick(); s2.zmiana()
        if s2.pietra[-1] == 9: break
    (tmp / "STOP_RECZNY").write_text("")
    bot.STOP = tmp / "STOP"          # istnieje tylko STOP_RECZNY obok (STOP usunięty)
    (tmp / "STOP").unlink()
    _os.environ.pop("RETRONIC_TESTY", None)
    try:
        try:
            b2.tick(); wyj2 = None
        except bot.Zatrzymano as e:
            wyj2 = e
    finally:
        bot.STOP = stare_stop
        _os.environ["RETRONIC_TESTY"] = "1"
    sprawdz("37j' STOP_RECZNY w wypadzie: też Zatrzymano, wypad zablokowany (nie wznawia się sam)",
            wyj2 is not None and b2.wyprawa.zablokowany and not b2.wypad_aktywny, f"{wyj2}")
    # ALARM_GM: wypad_przerwij -> koniec natychmiast, bot nie wraca do wypadu mimo spełnionych warunków
    s3 = Swiat37(start37()); b3 = zrob37(s3)
    for i in range(3000):
        b3.tick(); s3.zmiana()
        if s3.pietra[-1] == 10: break
    b3.wypad_przerwij("ALARM_GM")
    bieg(b3, s3, 60)
    sprawdz("37j'' ALARM_GM: wypad przerwany, zablokowany, wypad_koniec(przerwany), brak wznowienia mimo braku pochodni",
            not b3.wypad_aktywny and b3.wyprawa.zablokowany and ev(s3, "wypad_koniec")[-1]["wynik"] == "przerwany"
            and len(ev(s3, "wypad_start")) == 1 and not s3.mowa, f"{ev(s3, 'wypad_koniec')}")

    # 37k. drabina (ZMIANA CELOWA: wcześniej lina): dwa pierwsze Ctrl+kliki bez efektu -> trzeci działa; nigdy -> lina; nic -> awaria
    s = Swiat37(start37()); s.drab_psuje = 1; s.drab_tryb = 'cel'; b = zrob37(s)
    bieg37(b, s)
    sprawdz("37k drabina: pierwszy Ctrl+klik na każdej drabinie bez efektu (wypad_blad drabina_bez_zmiany_pietra), drugi działa, wypad dokończony, bez liny",
            ev(s, "wypad_koniec") and ev(s, "wypad_koniec")[0]["wynik"] == "ok"
            and sum(1 for d in ev(s, "wypad_blad") if d["rodzaj"] == "drabina_bez_zmiany_pietra") == 4
            and s.rope_wywolania == 0,
            f"błędy={[d['rodzaj'] for d in ev(s, 'wypad_blad')]} lina={s.rope_wywolania}")
    s = Swiat37(start37()); s.drab_tryb = 'wlasne'; b = zrob37(s)
    bieg37(b, s)
    sprawdz("37k2 drabina reaguje tylko na Ctrl+klik we własne pole (0,0): po 2 nieudanych klikach w drabinę wypad dokończony, bez liny",
            ev(s, "wypad_koniec") and ev(s, "wypad_koniec")[0]["wynik"] == "ok" and s.rope_wywolania == 0
            and s.poz[2] == 11, f"kon={ev(s, 'wypad_koniec')} lina={s.rope_wywolania}")
    s = Swiat37(start37()); s.drab_tryb = None; b = zrob37(s)
    bieg37(b, s)
    sprawdz("37k3 drabina nie działa wcale: kolejność prób cel,cel,własne,E,W,N, na końcu lina (fallback) -> wypad dokończony",
            ev(s, "wypad_koniec") and ev(s, "wypad_koniec")[0]["wynik"] == "ok" and s.rope_wywolania >= 1
            and s.drab_wywolania >= 5, f"kon={ev(s, 'wypad_koniec')} lina={s.rope_wywolania} drab={s.drab_wywolania}")
    s = Swiat37(start37()); s.drab_tryb = None; s.rope_dziala = False; b = zrob37(s)
    bieg37(b, s, maks=8000)
    kon = ev(s, "wypad_koniec")
    sprawdz("37k' ani drabina, ani lina: nie wisimy; awaria, powrót na z11 bez zakupów, porażka",
            kon and kon[0]["wynik"] != "ok" and s.poz[2] == 11 and s.rope_wywolania >= 1 and not s.mowa,
            f"kon={kon} lina={s.rope_wywolania} piętra={s.pietra}")

    # 37l. z7 -> z8: kratka bez flagi (Use zadziała), a w wariancie z krokiem (dziura bez flagi) - krok
    s = Swiat37(start37()); s.grate_krok = True; s.uzyj_dziala = False; b = zrob37(s)
    bieg37(b, s)
    sprawdz("37l z7->z8 gdy tylko krok działa (bez Use): próba Use zawodzi, krok przechodzi; wypad dokończony",
            ev(s, "wypad_koniec") and ev(s, "wypad_koniec")[0]["wynik"] == "ok" and s.poz[2] == 11,
            f"błędy={[(d['rodzaj'], d.get('tryb')) for d in ev(s, 'wypad_blad')]}")

    # 37m. przerwy mózgu nie przerywają wypadu: PRZERWA odroczona w wypadzie
    s = Swiat37(start37()); b = zrob37(s)
    b.przerwa_od = s.t - 1
    for i in range(300):
        b.tick(); s.zmiana()
        if b.wypad_aktywny: break
    sprawdz("37m w wypadzie przerwa od gry (PRZERWA) nie zatrzymuje marszu", b.wypad_aktywny and b.stan != "PRZERWA", f"stan={b.stan}")

    # 37n. pokrętła: analityk nie wyłączy wypadu, nie zmniejszy zapasu
    dom = {"WYPAD_PO_TORCHE": 1, "WYPAD_ILE_TORCHY": 5, "WYPAD_JEDZENIE": 1}
    ok_, bl_ = _pok37.waliduj({"WYPAD_PO_TORCHE": 0, "WYPAD_ILE_TORCHY": 3, "WYPAD_JEDZENIE": 0}, dom)
    ok2, bl2 = _pok37.waliduj({"WYPAD_ILE_TORCHY": 8}, dom)
    sprawdz("37n pokrętła wypadu: wyłączenie/zmniejszenie odrzucone, zwiększenie WYPAD_ILE_TORCHY przyjęte",
            not ok_ and len(bl_) == 3 and ok2 == {"WYPAD_ILE_TORCHY": 8}
            and cavebot.WYPAD_PO_TORCHE is True and cavebot.WYPAD_ILE_TORCHY == 5 and cavebot.WYPAD_ZAKUPY == {"torch": 5},
            f"{ok_} {bl_} {ok2}")
    s = Swiat37(start37()); cavebot.WYPAD_ILE_TORCHY = 8; b = zrob37(s)
    try:
        sprawdz("37n' WYPAD_ILE_TORCHY=8 (pokrętło) podnosi cel zakupu torch do 8", dict(b.wyprawa.zakupy()) == {"torch": 8})
    finally:
        cavebot.WYPAD_ILE_TORCHY = 5
    cavebot.WYPAD_PO_TORCHE = False; cavebot.WYPAD_JEDZENIE = False
    try:
        s, b = swiat_b()
        sprawdz("37n'' obie flagi False: brak wypadu (ręczne wyłączenie w kodzie)", not okazja_po(s, b, 4))
    finally:
        cavebot.WYPAD_PO_TORCHE = True; cavebot.WYPAD_JEDZENIE = True
    for k, v in _stare_wypad.items(): setattr(cavebot, k, v)

# U1. unikanie zwykłych graczy (unikanie.py): zmiana punktu rotacji, pomijanie celów przy graczu, bez zatrzymania
def swiat_u1(gracz=(112, 100), mob=None, poz=(100, 100, 7), **kw):
    sala_u = [(a, c) for a in range(90, 141) for c in range(90, 111)]
    s = Swiat(poz=poz)
    s.stwory = []
    if gracz: s.stwory.append({"id": 77, "nazwa": "Zbyszek", "gracz": True, "x": gracz[0], "y": gracz[1], "z": 7, "hp": 100})
    if mob: s.stwory.append({"id": 5, "nazwa": "Rat", "gracz": False, "x": mob[0], "y": mob[1], "z": 7, "hp": 100})
    b = zrob_lab(s, [(100 + i, 100, 7) for i in range(1, 31)], mapa=AtrapaMapy(sala_u), okrazenia=50, **kw)
    labirynt(s, sala_u)
    zd_ = []
    b.unikanie.zdarzenie = lambda typ, **d: zd_.append((typ, d))
    s.zd_u = zd_
    return s, b
def cheb_u(s, p): return max(abs(s.poz[0] - p[0]), abs(s.poz[1] - p[1]))
# U1a. gracz stoi na trasie 12 pól przed nami: po debounce omijamy go, trzymamy >= 3 pola, nie stoimy
s, b = swiat_u1()
s.zabija = False
min_, poz_t = 99, []
for _ in range(120):
    b.tick(); poz_t.append((s.t, tuple(s.poz[:2]))); min_ = min(min_, cheb_u(s, (112, 100)))
sprawdz("U1a gracz na trasie: unikanie włączone, zdarzenie unikanie_start z nickiem i odległością",
        b.unikanie.aktywne and [d for t, d in s.zd_u if t == "unikanie_start"][:1]
        and [d for t, d in s.zd_u if t == "unikanie_start"][0]["gracz"] == "Zbyszek", s.zd_u[:2])
sprawdz("U1b nie podchodzimy do gracza bliżej niż 3 pola (start 12 pól od niego)", min_ >= 3, f"min={min_}")
sprawdz("U1c bot nie zamarza: pozycja zmienia się, nie ma alarmu ani stanu GRACZ",
        len({p for _, p in poz_t}) >= 8 and not s.alarmy and b.stan != "GRACZ", f"pola={len({p for _, p in poz_t})} stan={b.stan}")
sprawdz("U1d log po polsku (Unikanie: ...)", any(l.startswith("Unikanie:") for l in cavelog[-200:]), cavelog[-3:])
# U1e. mob 3 pola od gracza nie jest celem; po zniknięciu gracza (10 s) bot go bije
s, b = swiat_u1(gracz=(110, 100), mob=(107, 100), poz=(104, 100, 7))
s.zabija = False
for _ in range(10): b.tick()
sprawdz("U1e mob przy graczu (3 pola) nie jest celem: brak ataków, brak 'Nowy cel'", s.ataki == [] and b.cel is None, s.ataki)
s.stwory[:] = [m for m in s.stwory if not m.get("gracz")]
for _ in range(120):
    b.tick()
    if s.ataki: break
sprawdz("U1e2 gracz zniknął: mob przestaje być pomijany i jest celem (histereza 10 s dotyczy tylko trasy)", s.ataki != [], (s.ataki, b.unikanie.aktywne))
# U1f. mob obok nas, gracz 2 pola od moba: bijemy (nie kradniemy, tylko bronimy się)
s, b = swiat_u1(gracz=(106, 100), mob=(103, 100), poz=(102, 100, 7))
s.zabija = False
for _ in range(6): b.tick()
sprawdz("U1f mob obok nas jest bity mimo gracza obok moba", s.ataki != [], s.ataki)
# U1g. --ignoruj-graczy: unikanie nieaktywne (bot idzie po staremu)
s, b = swiat_u1(zatrzymaj_przy_graczu=False)
s.zabija = False
for _ in range(30): b.tick()
sprawdz("U1g --ignoruj-graczy: brak unikania", not b.unikanie.aktywne and b.unikanie.gracze == [], b.unikanie.gracze)
# U1h. pokrętła: stałe UNIKANIE_* w pokretla.py (analityk nie może wyłączyć)
import pokretla as _pk
ok_, bl_ = _pk.waliduj({"UNIKANIE": 0}, {"UNIKANIE": cavebot.UNIKANIE})
sprawdz("U1h pokrętło UNIKANIE=0 od analityka odrzucone; w górę/ręcznie dozwolone",
        ok_ == {} and bl_ and _pk.waliduj({"UNIKANIE": 1}, {"UNIKANIE": 1})[0] == {"UNIKANIE": 1}
        and _pk.waliduj({"UNIKANIE": 0})[0] == {"UNIKANIE": 0}, (ok_, bl_))
sprawdz("U1i wszystkie UNIKANIE_* z ZAKRESY mają stałą w cavebot.py",
        all(hasattr(cavebot, k) for k in _pk.ZAKRESY if k.startswith("UNIKANIE")), [k for k in _pk.ZAKRESY if k.startswith("UNIKANIE") and not hasattr(cavebot, k)])


# 40. zmiany 11.10 (Q3/Q4/Q5, S4, pamięć MAKS_ODL, telemetria puszczeń)
sprawdz("40a domyślne: POSCIG_TRZYMAJ_PRZEGLAD 1.0, PRZERWA_PO_ZAWROCIU 1.0, STUK_PO_OSCYLACJI 1.5, PAMIEC_MAKS_ODL 5",
        cavebot.POSCIG_TRZYMAJ_PRZEGLAD == 1.0 and cavebot.POSCIG_PRZERWA_PO_ZAWROCIE == 1.0
        and cavebot.POSCIG_STUK_PO_OSCYLACJI == 1.5 and cavebot.POSCIG_PAMIEC_MAKS_ODL == 5
        and cavebot.POSCIG_OSTATNI_TRZYMAJ is True and cavebot.POSCIG_PAUZA_TICK_DALEKO == (0.0, 0.03))
_k = __import__("klawisz_x11")
sprawdz("40a2 strażnik klawiszy nadal 0.6 s (puls wokół przeglądu zamiast podnoszenia stałej)", _k.WATCHDOG_S == 0.6)

# 40b. S4: _poscig_decyzja w "ostatni": cel dokładnie przed nami na kierunku marszu = trzymamy; inaczej puszczamy
s, b = swiat_trzymaj(cel_x=106)
_d = lambda xy, v: b._poscig_decyzja({"x": xy[0], "y": xy[1]}, (100, 100, 7), v, set())
r_przod = _d((102, 100), (1, 0))      # q=(101,100), cel na (102,100): przed nami
r_bok = _d((101, 101), (1, 0))        # cel obok kroku (nie na kierunku marszu)
sprawdz("40b S4: cel przed nami: klawisz trzymany dalej (want = v_krok, powód ostatni_trzymany)",
        r_przod == ((1, 0), False, "ostatni_trzymany"), r_przod)
sprawdz("40b2 S4: cel z boku kroku: jak dawniej, puszczenie (None, 'ostatni')", r_bok == (None, False, "ostatni"), r_bok)
cavebot.POSCIG_OSTATNI_TRZYMAJ = False
cavebot.POSCIG_OSTATNI_DOCISKAJ = False      # 12.10: dociskanie obejmuje też ten przypadek (patrz 42)
try:
    r_wyl = _d((102, 100), (1, 0))
finally:
    cavebot.POSCIG_OSTATNI_TRZYMAJ = True
    cavebot.POSCIG_OSTATNI_DOCISKAJ = True
sprawdz("40b3 POSCIG_OSTATNI_TRZYMAJ=False: dawne puszczanie", r_wyl == (None, False, "ostatni"), r_wyl)

# 40c. telemetria poscig_koniec: puszczenia (per powód), kliki_ataku, t_pierwszy_krok; przegląd z pulsem
_random.seed(5)
s, b = swiat_trzymaj(cel_x=106)
start_poscig(s, b); k = odrzut(s, b)
sprawdz("40c poscig_koniec: puszczenia {'wyjscie': 1}, kliki_ataku liczba, t_pierwszy_krok > 0",
        k.get("puszczenia") == {"wyjscie": 1} and isinstance(k.get("kliki_ataku"), int)
        and k.get("t_pierwszy_krok") is not None and 0 < k["t_pierwszy_krok"] < 1.5, k)
cavebot.POSCIG_OSTATNI_TRZYMAJ = False
cavebot.POSCIG_OSTATNI_DOCISKAJ = False      # 12.10: bez dociskania dawne puszczenie z powodem 'ostatni'
try:
    _random.seed(5)
    s, b = swiat_trzymaj(cel_x=106)
    start_poscig(s, b); k0 = odrzut(s, b)
finally:
    cavebot.POSCIG_OSTATNI_TRZYMAJ = True
    cavebot.POSCIG_OSTATNI_DOCISKAJ = True
sprawdz("40c2 bez S4 puszczenie liczone z powodem 'ostatni'", (k0.get("puszczenia") or {}).get("ostatni") == 1, k0)
# przegląd: puls przed, między gracz/stwory i po (tryb trzymania)
s, b = swiat_trzymaj(cel_x=106)
_p0 = s.pulsy
b._poscig_przeglad({"id": 1, "nazwa": "Rat", "x": 106, "y": 100}, (100, 100, 7), None, puls=True)
sprawdz("40d _poscig_przeglad(puls=True): 3 pulsy strażnika", s.pulsy - _p0 == 3, s.pulsy - _p0)
_p0 = s.pulsy
b._poscig_przeglad({"id": 1, "nazwa": "Rat", "x": 106, "y": 100}, (100, 100, 7), None)
sprawdz("40d2 bez puls: bez pulsów (stuk jak dawniej)", s.pulsy == _p0)

# 40e. Q5: pauza po ticku
for odl_t, maks in ((3, 0.03), (None, None), (1, None)):
    s = Swiat(); b = zrob(s, trasa(), okrazenia=1)
    sen = []
    b.spij = lambda d: sen.append(d)
    b.walka_odl_tick = odl_t
    b.pauza_po_ticku()
    if maks is not None:
        sprawdz(f"40e pauza_po_ticku przy odl {odl_t}: <= 0.03 s", sen and sen[0] <= maks, sen)
    else:
        sprawdz(f"40e pauza_po_ticku przy odl {odl_t}: 0.05-0.15 s", sen and 0.05 <= sen[0] <= 0.15, sen)

# 40f. pamięć: cel zniknął dalej niż POSCIG_PAMIEC_MAKS_ODL = bez pościgu na pamięć (w 33a cel znika 5 pól od nas)
if True:
    _mm = cavebot.POSCIG_PAMIEC_MAKS_ODL
    try:
        cavebot.POSCIG_PAMIEC_MAKS_ODL = 3
        cavelog.clear()
        s, b, sw = swiat33()
        bieg(b, s, 20, sw)
        st = zdarz33(s, "poscig_pamiec_start")
        sprawdz("40f cel zniknął > POSCIG_PAMIEC_MAKS_ODL pól: brak pościgu na pamięć + wpis w logu",
                not st and b.pamiec is None and any("bez pościgu na pamięć" in l for l in cavelog), (st, cavelog[-5:]))
        cavebot.POSCIG_PAMIEC_MAKS_ODL = 5
        s, b, sw = swiat33()
        bieg(b, s, 20, sw)
        sprawdz("40f2 przy MAKS_ODL=5 (domyślnie) ten sam scenariusz startuje pościg na pamięć",
                len(zdarz33(s, "poscig_pamiec_start")) == 1, zdarz33(s, "poscig_pamiec_start"))
    finally:
        cavebot.POSCIG_PAMIEC_MAKS_ODL = _mm

# 41. POSCIG_VKROK_SCIANA (11.10): trzymany klawisz po dojściu prowadzi w ścianę (kierunek poprzedniego kroku, a droga
# skręca): krok nie trwa, decyzja z poz = skręt, a nie fałszywe "zawracanie" (telemetria: 34 z 39 zawróceń)
def _vk(v_krok, cel, sciana=None, zaj=None, hist=None, dodatkowe=()):
    s, b = swiat_trzymaj(cel_x=130)
    poz = (32030, 32150, 11)
    for sc in ([sciana] if sciana else []) + list(dodatkowe):
        b.sciany[sc] = b.zegar()
    zaj = set(zaj or ())
    s_d = {"x": cel[0], "y": cel[1]}
    want, objazd, powod = b._poscig_decyzja(s_d, poz, v_krok, zaj)
    q = poz if (v_krok is None or (sciana and cavebot.POSCIG_VKROK_SCIANA)) else (poz[0] + v_krok[0], poz[1] + v_krok[1], poz[2])
    st = {"ost": v_krok, "t_zm": 0.0, "hist": hist or [(32029, 32150, 1.0), (32030, 32150, 1.3)]}
    if want is not None:
        want, filtr = b._poscig_stabilny(want, q, cel, v_krok, zaj, st, 1.4)
    else:
        filtr = None
    return want, powod, filtr
_SC = (32030, 32151, 11)
_SC2 = [(32031, 32151, 11)]   # ściana też na wschód od ściany: z q (na ścianie) nie ma drogi do celu poza cofnięciem
w, pw, fl = _vk((0, 1), (32036, 32151), sciana=_SC, dodatkowe=_SC2)
sprawdz("41a trzymany [0,1] w ścianę (32030,32151), cel (32036,32151): skręt na wschód, nie 'zawroc'",
        w == (1, 0) and fl != "zawroc", (w, pw, fl))
cavebot.POSCIG_VKROK_SCIANA = False
try:
    w0, pw0, fl0 = _vk((0, 1), (32036, 32151), sciana=_SC, dodatkowe=_SC2)
finally:
    cavebot.POSCIG_VKROK_SCIANA = True
sprawdz("41b pokrętło wyłączone = stare zachowanie (q liczone ze ściany: brak skrętu na wschód; filtr cofnięcia)",
        w0 != (1, 0) and fl0 in ("zawroc", "pingpong"), (w0, pw0, fl0))
# 41c. kontrola: prawdziwe zawracanie celu (cel za nami, na polu z historii), klawisz NIE w ścianę: nadal 'zawroc'
w, pw, fl = _vk((1, 0), (32020, 32150), hist=[(32029, 32150, 1.0), (32030, 32150, 1.3)])
sprawdz("41c prawdziwe zawracanie (cel za nami, pole za nami w historii, klawisz nie w ścianę): 'zawroc'",
        w is None and fl == "zawroc", (w, pw, fl))
# 41d. to samo przy ścianie PRZED nami i celu za nami: zawracanie dalej wykrywane
w, pw, fl = _vk((1, 0), (32020, 32150), sciana=(32031, 32150, 11), hist=[(32029, 32150, 1.0), (32030, 32150, 1.3)])
sprawdz("41d klawisz w ścianę, ale cel naprawdę za nami (pole za nami w historii): nadal 'zawroc'",
        w is None and fl == "zawroc", (w, pw, fl))
# 41e. pole przed nami zajęte przez stwora (zaj) = też nie krok w toku
w, pw, fl = _vk((0, 1), (32036, 32151), zaj={(32030, 32151)})
sprawdz("41e trzymany klawisz na zajęte pole: skręt na wschód", w == (1, 0) and fl != "zawroc", (w, pw, fl))
# 41f. pokrętło w pokretla.py
import pokretla as _pk
sprawdz("41f pokretla: POSCIG_VKROK_SCIANA w ZAKRESY (0,1) i KIERUNEK",
        _pk.ZAKRESY.get("POSCIG_VKROK_SCIANA") == (0, 1) and "POSCIG_VKROK_SCIANA" in _pk.KIERUNEK
        and cavebot.POSCIG_VKROK_SCIANA is True)

# 23. loot pod nogami (12.10): alternatywne pola kandydatów, budżet prób, kolejna runda, pokrętło
import types as _t23
def _loot23(wyniki, niedok):
    wyw = []
    def zb(zwloki, gracz):
        wyw.append({"zw": tuple(zwloki), "alt": list(ns.ALTERNATYWY), "pod": ns.POD_NOGAMI_PIERWSZE, "maks": ns.MAKS_PROB})
        ns.NIEDOKONCZONE = niedok and len(wyw) < len(wyniki)
        return wyniki[len(wyw) - 1]
    ns = _t23.SimpleNamespace(zbierz=zb, PROBOWANE={}, NIEDOKONCZONE=False)
    return ns, wyw
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
b.loot, wyw = _loot23(["ok"], False)
b.loot_alternatywy = [(100, 100)]
b.zbierz_loot((101, 100, 7))
sprawdz("23a loot dostaje alternatywy (pole gracza), flagę i budżet",
        wyw and wyw[0]["alt"] == [(100, 100)] and wyw[0]["pod"] is True and wyw[0]["maks"] == cavebot.LOOT_MAKS_PROB,
        f"{wyw}")
# 23b. budżet wyczerpany: druga runda bez zejścia, potem ok (12.10: domyślnie RETRY_DALEJ=0, tu testujemy mechanizm rund)
cavebot.LOOT_RETRY_DALEJ, cavebot.LOOT_PONOW_LOKALNIE = 2, 0
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
b.loot, wyw = _loot23(["brak_okna", "brak_okna", "ok"], True)
w = b.zbierz_loot((101, 100, 7))
sprawdz("23b budżet pól wyczerpany -> kolejne rundy (3 wywołania), wynik ok", len(wyw) == 3 and w == "ok", f"{len(wyw)} {w}")
# 23c. nie więcej niż LOOT_RETRY_DALEJ dodatkowych rund
s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
b.loot, wyw = _loot23(["brak_okna"] * 6, True)
b.loot.zbierz_orig = b.loot.zbierz
def _zb_stale(zw, gr):
    r = b.loot.zbierz_orig(zw, gr); b.loot.NIEDOKONCZONE = True; return r
b.loot.zbierz = _zb_stale
w = b.zbierz_loot((101, 100, 7))
sprawdz("23c rund najwyżej 1 + LOOT_RETRY_DALEJ", len(wyw) == 1 + cavebot.LOOT_RETRY_DALEJ and w == "brak_okna", f"{len(wyw)} {w}")
cavebot.LOOT_RETRY_DALEJ, cavebot.LOOT_PONOW_LOKALNIE = 0, 1     # domyślne po zmianie 12.10
# 23d. pokrętło wyłączone: loot dostaje False, brak alternatyw i dodatkowych rund
cavebot.LOOT_POD_NOGAMI_PIERWSZE = False
try:
    s = Swiat(poz=(100,100,7)); b = zrob(s, trasa())
    b.loot, wyw = _loot23(["brak_okna", "ok"], True)
    b.loot_alternatywy = [(100, 100)]
    w = b.zbierz_loot((101, 100, 7))
finally:
    cavebot.LOOT_POD_NOGAMI_PIERWSZE = True
sprawdz("23d pokrętło wyłączone: stare zachowanie (1 wywołanie, bez alternatyw, pod=False)",
        len(wyw) == 1 and wyw[0]["alt"] == [] and wyw[0]["pod"] is False and w == "brak_okna", f"{wyw} {w}")
sprawdz("23e pokretla: LOOT_POD_NOGAMI_PIERWSZE (0,1) w ZAKRESY i KIERUNEK, LOOT_MAKS_PROB w ZAKRESY",
        _pk.ZAKRESY.get("LOOT_POD_NOGAMI_PIERWSZE") == (0, 1) and "LOOT_POD_NOGAMI_PIERWSZE" in _pk.KIERUNEK
        and "LOOT_MAKS_PROB" in _pk.ZAKRESY and cavebot.LOOT_POD_NOGAMI_PIERWSZE is True)
# 23f. zgon_celu: kandydaci (poz+krok, poz) -> alternatywą jest drugie pole; pierwszy brak_okna -> drugi kandydat
s = Swiat(poz=(100,100,7), hp=100); s.stwory = [{"id": 92, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 30}]
b = zrob(s, trasa()); s.zabija = False
wyw = []
def zb23(zwloki, gracz):
    wyw.append((tuple(zwloki), list(b.loot.ALTERNATYWY)))
    return "brak_okna" if len(wyw) == 1 else "ok"
b.loot = types.SimpleNamespace(zbierz=zb23, PROBOWANE={}, NIEDOKONCZONE=False)
b.tick(); b.tick()
s.stwory[0]["y"] = 101; b.tick()
s.stwory.clear(); bieg(b, s, 6)
sprawdz("23f zgon w ruchu: alternatywą pierwszego pola jest ostatnia widziana pozycja",
        len(wyw) >= 2 and wyw[0][0] == (101, 101, 7) and (101, 100) in wyw[0][1] and (101, 102) in wyw[0][1]
        and wyw[1][0] == (101, 100, 7), f"{wyw}")

# --- 38. wymiana pochodni w trakcie zaplanowanej przerwy (PRZERWA; POCHODNIA_W_PRZERWIE) ---
def _przerwa38():
    s = Swiat(poz=(100,100,7), hp=100); s.stwory = []
    b = zrob(s, trasa())
    wyw = []
    stan = {"wypalona": True}
    def tick(teraz=None, bezpiecznie=True):
        wyw.append(s.t)
        if stan["wypalona"]:
            stan["wypalona"] = False      # wymiana wykonana: drag&drop + Ctrl+klik, potem pochodnia świeci
            return True
        return False
    b.pochodnia = types.SimpleNamespace(tick=tick)
    b.przerwa_od = s.t - 1
    return s, b, wyw, stan
s, b, wyw, stan = _przerwa38()
b.tick()
do0 = b.przerwa_do
sprawdz("38a przerwa ruszyła, pochodnia wypalona + zapas: wymiana wykonana w pierwszym ticku przerwy (POCHODNIA)",
        do0 is not None and len(wyw) == 1 and stan["wypalona"] is False and b.stan == "POCHODNIA", f"do={do0} wyw={wyw} stan={b.stan}")
b.tick(); b.tick()
sprawdz("38b po wymianie przerwa trwa dalej do wylosowanego końca (licznik nietknięty, stan PRZERWA, bez ruchu)",
        b.przerwa_do == do0 and b.stan == "PRZERWA" and tuple(s.poz) == (100, 100, 7), f"do={b.przerwa_do} stan={b.stan} poz={s.poz}")
s.t = do0 + 1; b.tick()
sprawdz("38c po końcu wylosowanego czasu przerwa się kończy (przerwa_do=None) i bot idzie dalej",
        b.przerwa_do is None and b.stan != "PRZERWA", f"do={b.przerwa_do} stan={b.stan}")
# 38d. pokrętło wyłączone: stare zachowanie (w przerwie pochodnia nie jest sprawdzana)
cavebot.POCHODNIA_W_PRZERWIE = False
try:
    s, b, wyw, stan = _przerwa38()
    b.tick(); b.tick(); b.tick()
finally:
    cavebot.POCHODNIA_W_PRZERWIE = True
sprawdz("38d POCHODNIA_W_PRZERWIE=False: w przerwie bez wymiany (stare zachowanie), przerwa trwa",
        not wyw and stan["wypalona"] and b.stan == "PRZERWA" and b.przerwa_do is not None, f"wyw={wyw} stan={b.stan}")
# 38e. żywy stwór w pobliżu: _pochodnia_tick własną ochroną nie wymienia (tick pochodni niewołany)
s, b, wyw, stan = _przerwa38()
s.stwory = [{"id": 93, "nazwa": "Rat", "gracz": False, "x": 103, "y": 100, "z": 7, "hp": 100}]
b.zywy_w_poblizu = lambda lista, poz: {"nazwa": "Rat"}
b._pochodnia_tick  # metoda zwykła, ochrona wewnątrz
r = b._pochodnia_tick([], (100, 100, 7))
sprawdz("38e _pochodnia_tick z żywym w pobliżu: bez wymiany (ochrona jak poza przerwą)", r is False and not wyw, f"r={r} wyw={wyw}")
sprawdz("38f pokretla: POCHODNIA_W_PRZERWIE (0,1) w ZAKRESY i KIERUNEK, domyślnie True",
        _pk.ZAKRESY.get("POCHODNIA_W_PRZERWIE") == (0, 1) and "POCHODNIA_W_PRZERWIE" in _pk.KIERUNEK
        and cavebot.POCHODNIA_W_PRZERWIE is True)

# 42. POSCIG_OSTATNI_DOCISKAJ (12.10): uciekający cel w odl 2, krok z klawisza kończy się przy nim: klawisz trzymany dalej
# (dawniej puszczany: postać stała ~1,3 s do ponowienia, szczur o kroku 1,5 s zostawał w odl 2-3 i było "odpuszczam po 25 s")
s, b = swiat_trzymaj(cel_x=106)
_d = lambda xy, v: b._poscig_decyzja({"x": xy[0], "y": xy[1]}, (100, 100, 7), v, set())
r_off = _d((102, 99), (1, 0))      # q=(101,100) przy celu (odl 1), a od poz odl 2, cel poza osią marszu
sprawdz("42a cel w odl 2 poza osią, krok kończy przy nim: klawisz trzymany dalej (ostatni_dociska)",
        r_off == ((1, 0), False, "ostatni_dociska"), r_off)
cavebot.POSCIG_OSTATNI_DOCISKAJ = False
try:
    r_off0 = _d((102, 99), (1, 0))
finally:
    cavebot.POSCIG_OSTATNI_DOCISKAJ = True
sprawdz("42b POSCIG_OSTATNI_DOCISKAJ=False: dawne puszczenie (None, 'ostatni')", r_off0 == (None, False, "ostatni"), r_off0)
r_obok = _d((101, 101), (1, 0))    # cel już obok (odl 1): bez zmian, puszczamy
sprawdz("42c cel już obok (odl 1): nadal (None, 'ostatni')", r_obok == (None, False, "ostatni"), r_obok)
sprawdz("42d pokrętło w ZAKRESY/KIERUNEK, domyślnie True",
        _pk.ZAKRESY.get("POSCIG_OSTATNI_DOCISKAJ") == (0, 1) and "POSCIG_OSTATNI_DOCISKAJ" in _pk.KIERUNEK
        and cavebot.POSCIG_OSTATNI_DOCISKAJ is True)


def swiat_ucieczka(cel_x=103, cel_y=99, krok_cel=1.5, start_cel=0.5, x_max=140, krok_gracza=0.88, lat=0.17):
    """Atrapa klienta jak na żywo (pomiar 12.10): pozycja gracza zmienia się na STARCIE kroku (po lat s od naciśnięcia
    z postoju), kolejny krok najwcześniej po krok_gracza s; klawisz puszczony przed startem kroku = krok przepada.
    Cel (szczur) ucieka w prawo o 1 pole co krok_cel s, od start_cel s, do x_max."""
    s, b = swiat_poscigu(cel_x=cel_x, opoznienie=krok_gracza, koszt=KOSZT_T)
    s.stwory[0]["y"] = cel_y            # sąsiednia kolumna/wiersz (korytarz 2-polowy): cel poza osią marszu
    s.trzym = None; s.pend = None; s.cd = 0.0; s.zd = []; s.pulsy = 0; s.taps = []
    s.cel_t = s.t + start_cel; s.kroki_celu = 0
    def advance():
        while s.pend is not None and s.t >= s.pend:
            tc = s.pend
            if s.trzym is not None:
                s.poz[0] += s.trzym[0]; s.poz[1] += s.trzym[1]; s.pozycje_czasy.append(tc)
                s.cd = tc + krok_gracza
                s.pend = s.cd
            else:
                s.pend = None
        while s.cel_t <= s.t and s.stwory[0]["x"] < x_max:
            if s.stwory[0]["x"] - s.poz[0] >= 1:
                s.stwory[0]["x"] += 1; s.kroki_celu += 1
            s.cel_t += krok_cel
    def trzymaj_kierunek(dx, dy):
        advance()
        s.zd.append((round(s.t, 2), "zmien" if s.trzym else "nacisnij", (dx, dy)))
        s.trzym = (dx, dy)
        if s.pend is None:
            s.pend = max(s.t + lat, s.cd)
    def puszczaj():
        advance()
        if s.trzym is not None: s.zd.append((round(s.t, 2), "puść", s.trzym))
        s.trzym = None
    def pozycja():
        s.t += 0.035; advance(); return tuple(s.poz)
    p = b.postac
    p.trzymaj_kierunek = trzymaj_kierunek; p.puszczaj = puszczaj; p.pozycja = pozycja
    p.trzymany_kierunek = lambda: s.trzym
    p.puls = lambda: setattr(s, "pulsy", s.pulsy + 1)
    p.klawisz = lambda k: s.taps.append(k)
    b.spij = lambda d: (setattr(s, "t", s.t + d), advance())
    return s, b


def bieg_ucieczki(dociskaj, cel_x=103):
    cavebot.POSCIG_OSTATNI_DOCISKAJ = dociskaj
    try:
        _random.seed(21)
        s, b = swiat_ucieczka(cel_x=cel_x)
        t0 = s.t
        wyniki = []
        for _ in range(6):               # kolejne okna pętli (jak kolejne obiegi tick), do dojścia obok celu
            start_poscig(s, b)
            k = zdarzenia(s, "poscig_koniec")[-1]
            wyniki.append(k)
            if k["powod"] == "odl<=1":
                break
        return s, b, wyniki, s.t - t0
    finally:
        cavebot.POSCIG_OSTATNI_DOCISKAJ = True

s1, b1, w1, t1 = bieg_ucieczki(True)
s0, b0, w0, t0_ = bieg_ucieczki(False)
print(f"     pomiar 42: dociskanie: {t1:.1f} s, kroki {[k['kroki'] for k in w1]}, powody {[k['powod'] for k in w1]}; "
      f"dawne: {t0_:.1f} s, kroki {[k['kroki'] for k in w0]}, powody {[k['powod'] for k in w0]}")
sprawdz("42e uciekający cel (krok 1,5 s) w odl 3, nasz krok 0,88 s: z dociskaniem dopadamy go (odl<=1) w < 8 s",
        w1[-1]["powod"] == "odl<=1" and t1 < 8.0, (t1, [k["powod"] for k in w1]))
sprawdz("42f dociskanie: cadence kroków <= 1,0 s (dawniej ~1,5 s po puszczeniu przy każdym kroku)",
        len(s1.pozycje_czasy) >= 3 and max(b_ - a_ for a_, b_ in zip(s1.pozycje_czasy, s1.pozycje_czasy[1:])) <= 1.0,
        [round(b_ - a_, 2) for a_, b_ in zip(s1.pozycje_czasy, s1.pozycje_czasy[1:])])
cad0 = [b_ - a_ for a_, b_ in zip(s0.pozycje_czasy, s0.pozycje_czasy[1:])]
sprawdz("42g dawne zachowanie (pokrętło False) w tej atrapie: wolniej (mediana kroku > 1,2 s) i nie szybciej dopada",
        (not cad0 or sorted(cad0)[len(cad0) // 2] > 1.2) and t0_ >= t1, (t0_, t1, [round(c, 2) for c in cad0]))
sprawdz("42h po wyjściu klawisz puszczony, a w telemetrii licznik ostatni_dociska",
        s1.trzym is None and any((k.get("filtry") or {}).get("ostatni_dociska") for k in w1), (s1.trzym, [k.get("filtry") for k in w1]))

# 43. skos awaryjny (12.10): jedyne przejście do celu po skosie (róg: dwa pola w osiach to ściana, pole po skosie wolne)
import mapa as _mapa_mod
class MapaRog(_mapa_mod.Mapa):
    """Prawdziwy A* z mapa.py na sztucznej mapie: wszystko ściana poza `wolne`, w obrębie ramki [x0..x1]x[y0..y1]."""
    def __init__(self, wolne, z=7, ramka=(80, 70, 130, 120)):
        self._bloki = {}; self._spis = {}; self._wolne = set(wolne); self._z = z; self._ramka = ramka
    def _blok(self, kb):
        b = self._bloki.get(kb)
        if b is None:
            z, bx, by = kb >> 20, (kb >> 10) & 1023, kb & 1023
            b = bytearray(64 * 64 * 3)
            x0, y0, x1, y1 = self._ramka
            if z == self._z:
                for j in range(64):
                    for i in range(64):
                        x, y = bx * 64 + i, by * 64 + j
                        if x0 <= x <= x1 and y0 <= y <= y1:
                            b[(j * 64 + i) * 3] = 1 if (x, y) in self._wolne else 5
            self._bloki[kb] = b
        return b
ROG_WOLNE = {(100, 100), (101, 99), (102, 98), (103, 97), (104, 96)}   # tylko przekątna: żadnego objazdu
def swiat_rog(**kw):
    s, b = swiat_trzymaj(cel_x=103, cel_y=97, **kw)
    b.mapa = MapaRog(ROG_WOLNE)
    return s, b
def sciany_ok(b): return not b.sciany

# 43a. pościg trzymanym klawiszem: skos (1,-1) numpadem, dojście obok celu, ściany nie nauczone
_random.seed(11)
s, b = swiat_rog()
r = start_poscig(s, b); k = odrzut(s, b)
sprawdz("43a róg: pościg wchodzi po skosie (1,-1) i dobija do odl<=1, bez nauki ścian",
        r is True and k["powod"] == "odl<=1" and any(z[2] == (1, -1) for z in s.zd) and tuple(s.poz[:2]) == (102, 98)
        and sciany_ok(b) and s.trzym is None, (r, k["powod"], s.zd, s.poz, b.sciany))
sprawdz("43a2 skos awaryjny policzony i zalogowany", b.skos_awaryjny_n >= 1 and any("Skos awaryjny" in l for l in cavelog[-30:]),
        (b.skos_awaryjny_n, cavelog[-3:]))

# 43b. pokrętło 0: dawne zachowanie (objazd, brak ruchu)
cavebot.POSCIG_SKOS_AWARYJNY = 0; cavebot.POSCIG_SKOSY_ZAPAS = 0   # R1c: stare zachowanie bez drugiej próby
try:
    _random.seed(11)
    s, b = swiat_rog()
    r = start_poscig(s, b)
    sprawdz("43b POSCIG_SKOS_AWARYJNY=0: brak drogi, objazd, postać stoi", r is None and tuple(s.poz[:2]) == (100, 100)
            and not any(z[2] == (1, -1) for z in s.zd), (r, s.poz, s.zd))
finally:
    cavebot.POSCIG_SKOS_AWARYJNY = 1; cavebot.POSCIG_SKOSY_ZAPAS = 1

# 43c. pole po skosie zajęte przez potwora: nie wchodzimy (objazd), brak naciśnięcia skosu
_random.seed(11)
s, b = swiat_rog()
mob2 = {"id": 78, "nazwa": "Troll", "gracz": False, "x": 101, "y": 99, "z": 7, "hp": 100}
s.stwory.append(mob2); s.zajete = {(101, 99)}
b.ostatnie_stwory = [mob2]
b.stwory = lambda wiek=None, m=mob2: [dict(s.stwory[0]), m]
r = start_poscig(s, b)
k43 = zdarzenia(s, "poscig_koniec")
sprawdz("43c skos zajęty przez potwora: bez wejścia, postać na (100,100), bez klawisza skosu",
        (r is None or (k43 and k43[-1]["kroki"] == 0)) and tuple(s.poz[:2]) == (100, 100)
        and not any(z[2] == (1, -1) for z in s.zd), (r, s.poz, s.zd, [d.get("powod") for d in k43]))

# 43d. tryb stuknięć (bez trzymania): numpad postac.skos, bez strzałek, dojście
cavebot.POSCIG_TRZYMAJ = False
try:
    _random.seed(11)
    s, b = swiat_poscigu(cel_x=103, opoznienie=0.25)
    s.stwory[0]["y"] = 97
    b.mapa = MapaRog(ROG_WOLNE)
    def skos_stuk(dx, dy):
        s.klawisze.append(("skos", dx, dy)); s.czasy_klawiszy.append(s.t)
        s.oczekuje = (s.t + s.opoznienie, s.poz[0] + dx, s.poz[1] + dy)
    b.postac.skos = skos_stuk
    r = start_poscig(s, b)
    sprawdz("43d stuknięcia: skos numpadem (1,-1) x2, dojście do (102,98), bez ścian",
            r is True and tuple(s.poz[:2]) == (102, 98) and s.klawisze.count(("skos", 1, -1)) == 2 and sciany_ok(b),
            (r, s.poz, s.klawisze, b.sciany))
finally:
    cavebot.POSCIG_TRZYMAJ = True

# 43e. krok_do: róg bez klika (strzałki): numpad postac.krok_skos, brak zmiany pozycji nie uczy ściany
class P43(P):
    def krok(p, k):          # strzałka w ścianę (poza ROG_WOLNE) nie rusza postaci
        d = bot.KIERUNKI[k]
        if (p.s.poz[0] + d[0], p.s.poz[1] + d[1]) not in ROG_WOLNE:
            return None
        return P.krok(p, k)
    def krok_skos(p, dx, dy):
        p.s.t += 0.2
        if p.s.skos_dziala:
            p.s.poz[0] += dx; p.s.poz[1] += dy; return tuple(p.s.poz)
        return None
s = Swiat(poz=(100, 100, 7)); s.skos_dziala = True
b = zrob(s, trasa()); b.postac = P43(s); b.mapa = MapaRog(ROG_WOLNE)
wynik = b.krok_do((101, 99, 7))
sprawdz("43e krok_do w rogu: skos numpadem, postać na (101,99), ściany bez zmian", wynik is True and tuple(s.poz) == (101, 99, 7)
        and sciany_ok(b), (wynik, s.poz, b.sciany))
s = Swiat(poz=(100, 100, 7)); s.skos_dziala = False
b = zrob(s, trasa()); b.postac = P43(s); b.mapa = MapaRog(ROG_WOLNE)
wynik = b.krok_do((101, 99, 7))
sprawdz("43e2 skos bez efektu: False, nie ściana (sciany puste), skos_zle zapamiętany", wynik is False and sciany_ok(b)
        and b.skos_zle, (wynik, b.sciany, b.skos_zle))
cavebot.POSCIG_SKOS_AWARYJNY = 0; cavebot.POSCIG_SKOSY_ZAPAS = 0   # R1c: stare zachowanie bez drugiej próby
try:
    s = Swiat(poz=(100, 100, 7)); s.skos_dziala = True
    b = zrob(s, trasa()); b.postac = P43(s); b.mapa = MapaRog(ROG_WOLNE)
    wynik = b.krok_do((101, 99, 7))
    sprawdz("43e3 pokrętło 0: krok_do nie robi skosu", wynik is False and tuple(s.poz) == (100, 100, 7), (wynik, s.poz))
finally:
    cavebot.POSCIG_SKOS_AWARYJNY = 1; cavebot.POSCIG_SKOSY_ZAPAS = 1

# 43f. podejdz poza pętlą pościgu (klik): droga ze skosem -> klik (1,-1); trasa: A* _droga_trasy daje skos
s = Swiat(poz=(100, 100, 7)); b = zrob_klik(s, trasa()); b.mapa = MapaRog(ROG_WOLNE)
wynik = b.podejdz((103, 97), (100, 100, 7), natychmiast=True, zajete=[])
sprawdz("43f podejdz (natychmiast, odl 3): klik w pole po skosie (1,-1), nie None", wynik is True and (1, -1) in s.kliki, (wynik, s.kliki))
d = b.droga((100, 100, 7), (104, 96), dlugosc=0)   # to wywołuje _droga_trasy (domyślnie skosy)
sprawdz("43f2 droga trasy (A*): przez skosy do (104,96)", d == [(101, 99, 7), (102, 98, 7), (103, 97, 7), (104, 96, 7)], d)
s = Swiat(poz=(100, 100, 7)); b = zrob_klik(s, trasa()); b.mapa = MapaRog(ROG_WOLNE)
cavebot.POSCIG_SKOS_AWARYJNY = 0; cavebot.POSCIG_SKOSY_ZAPAS = 0   # R1c: stare zachowanie bez drugiej próby
try:
    wynik = b.podejdz((103, 97), (100, 100, 7), natychmiast=True, zajete=[])
    sprawdz("43f3 pokrętło 0: podejdz None (objazd), brak kliku", wynik is None and not s.kliki, (wynik, s.kliki))
finally:
    cavebot.POSCIG_SKOS_AWARYJNY = 1; cavebot.POSCIG_SKOSY_ZAPAS = 1

# 43g. pokrętło w pokretla.py: zakres 0..1, kierunek nie_nizej
import pokretla as _pk
sprawdz("43g pokrętło POSCIG_SKOS_AWARYJNY w ZAKRESY (0,1), nie_nizej, domyślnie 1",
        _pk.ZAKRESY.get("POSCIG_SKOS_AWARYJNY") == (0, 1) and _pk.KIERUNEK.get("POSCIG_SKOS_AWARYJNY") == "nie_nizej"
        and cavebot.POSCIG_SKOS_AWARYJNY == 1)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
