"""Widmo 15.10 (1 h 45 min): po relogu dwa wpisy gracza i dwa bloki statystyk, stare zamrożone. Wybór ma iść za
ruchem wpisu i za żywym blokiem, nie za zgodnością z zamrożonym blokiem. Atrapy i wstrzyknięty zegar."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot, rdzen

ok = []
def sprawdz(n, w, info=""):
    ok.append(bool(w)); print(("OK   " if w else "FAIL ") + n + ("" if w else f"  [{info}]"))

# --- bot.wybierz_wlasny: ruch wpisu ---------------------------------------------------------------
WIDMO, ZYWY = 0x15d14728, 0x16cfa5f0
def wpis(adres, ident, x, y=32270, hp=100):
    return {"id": ident, "nazwa": "Jointoramix", "gracz": True, "x": x, "y": y, "z": 9, "hp": hp, "adres": hex(adres)}
# blok statystyk też jest widmem (adres tuż przy widmie, HP 100%): stara logika wskazuje widmo
G_WIDMO = {"hp": 210, "max_hp": 210, "adres": hex(0x15d14b98)}

def tick(ruch, widmo_x, zywy_x, t):
    kand = [wpis(WIDMO, 1, widmo_x), wpis(ZYWY, 2, zywy_x)]
    bot.sledz_ruch(ruch, kand, t)
    return kand

ruch = {}
kand = tick(ruch, 32506, 32500, 0.0)
sprawdz("start: bez ruchu stara logika (widmo przy bloku)", bot.wybierz_wlasny(kand, G_WIDMO, ruch, 0.0)["id"] == 1)
for t, x in ((2.0, 32501), (4.0, 32502)):
    kand = tick(ruch, 32506, x, t)
sprawdz("widmo stoi, żywy chodzi: wybrany żywy mimo bloku-widma", bot.wybierz_wlasny(kand, G_WIDMO, ruch, 4.0)["id"] == 2)
sprawdz("bez ruchu (ruch=None) zachowanie bez zmian", bot.wybierz_wlasny(kand, G_WIDMO)["id"] == 1)
sprawdz("po WLASNY_RUCH postoju zostaje jedyny wpis, który się kiedyś ruszał", bot.wybierz_wlasny(kand, G_WIDMO, ruch, 4.0 + bot.WLASNY_RUCH + 1)["id"] == 2)

ruch = {}
kand = tick(ruch, 32506, 32500, 0.0); kand = tick(ruch, 32506, 32500, 2.0)
sprawdz("oba stoją: stara logika (adres bloku)", bot.wybierz_wlasny(kand, G_WIDMO, ruch, 2.0)["id"] == 1)
G_ZYWY = {"hp": 196, "max_hp": 210, "adres": hex(0x16cfaa60)}
sprawdz("oba stoją, blok żywy: żywy wpis", bot.wybierz_wlasny(kand, G_ZYWY, ruch, 2.0)["id"] == 2)

ruch = {}
tick(ruch, 32506, 32500, 0.0); kand = tick(ruch, 32507, 32501, 2.0)
kand = tick(ruch, 32507, 32502, 4.0)
sprawdz("oba ruszone, świeższy ruch żywego", bot.wybierz_wlasny(kand, G_WIDMO, ruch, 4.0)["id"] == 2)
bot.sledz_ruch(ruch, [kand[1]], 6.0)
sprawdz("wpis znikający z listy znika ze słownika ruchu", len(ruch) == 1)

# --- rdzen._wybierz_blok_gracza: zamrożony blok bez zmian vs żywy -----------------------------------
class Zegar:
    t = 1000.0
    def __call__(s): return s.t
zegar = Zegar(); rdzen.time = type("T", (), {"monotonic": staticmethod(zegar), "sleep": rdzen.time.sleep, "time": rdzen.time.time})

class P(rdzen.Pamiec):
    def __init__(s):
        super().__init__(); s.bl = {}
    def blok_gracza(s, adres): return dict(s.bl[adres]) if adres in s.bl else None

def blok(hp, mana, exp): return {"hp": hp, "max_hp": 210, "cap": 1, "max_cap": 1, "exp": exp, "level": 1, "procent": 1, "mana": mana, "max_mana": 100}
STARY, NOWY = 0x15d14b98, 0x16cfaa60

p = P(); p.adres_gracza = STARY
p.bl = {STARY: blok(210, 87, 24965), NOWY: blok(196, 67, 25045)}
a, _ = p._wybierz_blok_gracza([STARY, NOWY])           # pierwszy odczyt obu: bez znanych zmian
sprawdz("zamrożony blok-widmo (obecny) vs żywy z wyższym exp: wybrany żywy", a == NOWY, hex(a))
p.adres_gracza = STARY
zegar.t += 25; a, _ = p._wybierz_blok_gracza([STARY, NOWY])   # żaden nie zmienił się między skanami
sprawdz("żywy bez zmian między skanami, nadal wyższe exp", a == NOWY, hex(a))

p = P(); p.adres_gracza = STARY
p.bl = {STARY: blok(210, 87, 24965), NOWY: blok(196, 67, 25045)}
p._wybierz_blok_gracza([STARY, NOWY])
zegar.t += 25; p.bl[NOWY] = blok(200, 70, 25045)
a, _ = p._wybierz_blok_gracza([STARY, NOWY])
sprawdz("żywy blok zmienił się od skanu: żywy", a == NOWY, hex(a))
zegar.t += bot.WLASNY_RUCH + 30      # żywy się uspokoił (>ZYWY_BLOK), widmo wciąż zamrożone
a, _ = p._wybierz_blok_gracza([STARY, NOWY])
sprawdz("po ustaniu zmian: exp rozstrzyga na korzyść żywego", a == NOWY, hex(a))

for obecny in (STARY, NOWY):
    p = P(); p.adres_gracza = obecny
    p.bl = {STARY: blok(210, 87, 25045), NOWY: blok(196, 67, 25045)}   # równe exp, nic się nie zmienia
    p._wybierz_blok_gracza([STARY, NOWY]); zegar.t += 25
    a, _ = p._wybierz_blok_gracza([STARY, NOWY])
    sprawdz(f"oba zamrożone, równe exp: zostaje obecny {hex(obecny)}", a == obecny, hex(a))

# gracz(): zamrożony blok w cache -> skan -> przełączenie na żywy
class P2(P):
    def szukaj_gracza(s): return [STARY, NOWY]
p = P2(); p.adres_gracza = STARY
p.bl = {STARY: blok(210, 87, 24965), NOWY: blok(196, 67, 25045)}
g = p.gracz(); zegar.t += 30
p.adres_gracza = STARY; g = p.gracz()
sprawdz("gracz(): po zamrożeniu >20 s skan przełącza na żywy blok", g["adres"] == hex(NOWY) and g["exp"] == 25045, g)

print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
