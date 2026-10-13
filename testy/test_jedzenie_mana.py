"""Jedzenie, gdy mana się nie regeneruje (JEDZENIE_MANA_BRAK_S). Wszystko na atrapach: klawisz/loot/czat to listy,
nic nie trafia do gry (RETRONIC_TESTY=1, brak XTEST)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla, powiadom

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s, mana=20, max_mana=35):
        s.t = 0.0; s.poz = [100, 100, 7]; s.mana = mana; s.max_mana = max_mana
        s.stwory = []; s.klawisze = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": s.mana, "max_mana": s.max_mana}}
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
        return tuple(p.s.poz)

def zrob(s, jedzenie="F5", okrazenia=1, **kw):
    zjedzone = []
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: (zjedzone.append(1), [])[1])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=okrazenia, jedzenie=jedzenie, **kw)
    b.przerwa_od = float("inf"); b.zjedzone_plecak = zjedzone
    return b

def g(s): return {"hp": 100, "max_hp": 100, "mana": s.mana, "max_mana": s.max_mana, "proc": 100.0}

def tick_g(b, s, dt):
    """Symuluje odczyt gracza w głównym ticku (śledzenie many jak w tick()) i pyta o jedzenie."""
    s.t += dt
    gr = g(s)
    return gr

# kontrakt: pokrętło
sprawdz("1a domyślnie 90 s", cavebot.JEDZENIE_MANA_BRAK_S == 90.0)
sprawdz("1b w ZAKRESY 30-600", pokretla.ZAKRESY.get("JEDZENIE_MANA_BRAK_S") == (30.0, 600.0))
sprawdz("1c KIERUNEK nie_wyzej", pokretla.KIERUNEK.get("JEDZENIE_MANA_BRAK_S") == "nie_wyzej")
sprawdz("1d analityk nie może wydłużyć",
        pokretla.waliduj({"JEDZENIE_MANA_BRAK_S": 300.0}, {"JEDZENIE_MANA_BRAK_S": 90.0})[0] == {})
sprawdz("1e analityk może skrócić",
        pokretla.waliduj({"JEDZENIE_MANA_BRAK_S": 60.0}, {"JEDZENIE_MANA_BRAK_S": 90.0})[0] == {"JEDZENIE_MANA_BRAK_S": 60.0})
sprawdz("1f 10 s odrzucone (poniżej zakresu)", pokretla.waliduj({"JEDZENIE_MANA_BRAK_S": 10.0})[0] == {})

# 2. pełna logika przez mana_nie_rosnie_s / jedzenie_potrzebne
def stan(b, s, nowa_mana=None):
    """Jak w tick(): aktualizacja śledzenia many po odczycie."""
    if nowa_mana is not None: s.mana = nowa_mana
    gr = g(s); teraz = s.t
    mana, mx = gr["mana"], gr["max_mana"]
    if b.mana_ostatnia is None or mana > b.mana_ostatnia or mana >= mx:
        b.mana_wzrost = teraz
    b.mana_ostatnia = mana
    return gr

s = Swiat(mana=20); b = zrob(s); stan(b, s)
s.t += 89; gr = stan(b, s)
sprawdz("2a 89 s bez wzrostu: jeszcze nie", not b.jedzenie_potrzebne(gr, s.t))
s.t += 2; gr = stan(b, s)
LOGI.clear()
sprawdz("2b 91 s bez wzrostu: głód", b.jedzenie_potrzebne(gr, s.t))
sprawdz("2c log 'Jedzenie: mana nie rośnie od X s'", any(l.startswith("Jedzenie: mana nie rośnie od 9") for l in LOGI), LOGI)
b.zjedz(s.t, gr)
sprawdz("2d klawisz jedzenia naciśnięty (atrapa)", s.klawisze == ["F5"], s.klawisze)
sprawdz("2e log stanu z many i ML", any("[JEDZENIE]" in l and "mana 20/35 (57%), ML off" in l for l in LOGI), LOGI)
sprawdz("2f zaraz po jedzeniu nie je znowu", not b.jedzenie_potrzebne(stan(b, s), s.t))

# 3. wzrost many resetuje zegar
s = Swiat(mana=20); b = zrob(s); stan(b, s)
s.t += 80; stan(b, s, 21)
s.t += 80; gr = stan(b, s)
sprawdz("3a mana +1 po 80 s: zegar od nowa", not b.jedzenie_potrzebne(gr, s.t))
s.t += 20; gr = stan(b, s)
sprawdz("3b 100 s po wzroście: głód", b.jedzenie_potrzebne(gr, s.t))

# 4. pełna mana, brak odczytu, rzut czaru
s = Swiat(mana=35); b = zrob(s); stan(b, s); s.t += 500; gr = stan(b, s)
sprawdz("4a pełna mana: bez jedzenia", not b.jedzenie_potrzebne(gr, s.t))
s = Swiat(mana=20); b = zrob(s); stan(b, s); s.t += 200
b.ml_ostatni = s.t - 30           # bot rzucił czar 30 s temu
gr = stan(b, s)
sprawdz("4b niedawny rzut czaru: bez jedzenia", not b.jedzenie_potrzebne(gr, s.t))
b.ml_ostatni = s.t - 100
sprawdz("4c rzut dawno temu: głód", b.jedzenie_potrzebne(gr, s.t))
gr = {"hp": 100, "max_hp": 100, "mana": None, "max_mana": None, "proc": 100.0}
s.t += 500
sprawdz("4d brak odczytu many: bez jedzenia", not b.jedzenie_potrzebne(gr, s.t))

# 5. blokady istniejącego mechanizmu: brak jedzenia, mob blisko
s = Swiat(mana=20); b = zrob(s); stan(b, s); s.t += 100; gr = stan(b, s)
b.jedzenie_nie_do = s.t + 100
sprawdz("5a jedzenie_nie_do (brak jedzenia) blokuje", not b.jedzenie_potrzebne(gr, s.t))
b.jedzenie_nie_do = float("-inf")
mob = {"id": 7, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}
b.ostatnie_stwory = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 7, "hp": 100}, mob]
sprawdz("5b mob w JEDZENIE_BLISKO: bez jedzenia", not b.jedzenie_potrzebne(gr, s.t, (100, 100, 7)))

# 6. bez klawisza: jedzenie z plecaka (loot.zjedz), brak jedzenia -> jedzenie_nie_do
s = Swiat(mana=20); b = zrob(s, jedzenie=None); b.klik = object(); stan(b, s); s.t += 100; gr = stan(b, s)
sprawdz("6a bez klawisza, z plecaka: głód many", b.jedzenie_potrzebne(gr, s.t, (100, 100, 7)))
b.zjedz(s.t, gr)
sprawdz("6b loot.zjedz wywołany, klawisz nie", b.zjedzone_plecak == [1] and s.klawisze == [])
sprawdz("6c brak jedzenia: jedzenie_nie_do ustawione", b.jedzenie_nie_do > s.t)

# 7. integracja w tick(): mana stoi, wołany pełny tick
s = Swiat(mana=20); b = zrob(s, okrazenia=10000)
for _ in range(3000):
    if not b.tick(): break
    if "F5" in s.klawisze: break
sprawdz("7a pełny tick: F5 po ~90 s braku wzrostu many", "F5" in s.klawisze and 85 <= s.t <= 140, f"t={s.t:.0f} {s.klawisze[:3]}")

# 8. podsumowanie powiadom: mana + ML
class T:
    def okno(s, n): return []
    def dobicie(s, n): return {}
t = T(); t.okno = lambda n: [{"typ": "probka", "stan": "IDZ", "hp": 100, "t": 1, "stwory": [], "mana": 10}]
import telemetria
_ag = telemetria.agreguj
pod = powiadom.Podsumowanie(zegar=lambda: 1000.0, wyslij=lambda a, c: None)
try:
    txt = pod.tekst(t, {"mana": 10, "max_mana": 40, "ml_aktywny": 1, "ml_rzuty": 3}, 1000.0)
except Exception as e:
    txt = f"BŁĄD {e!r}"
sprawdz("8a podsumowanie: mana i ML", "mana 10/40 (25%), ML on rzuty 3" in txt, txt)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
