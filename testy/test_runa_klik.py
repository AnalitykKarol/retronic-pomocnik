"""Strzał runą kliknięciami (RUNA_TRYB_KLIK): na atrapach, bez X11 i bez prawdziwych klików (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import cavebot, bot, pokretla, runa_klik

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0
cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Env:
    """Atrapa środowiska klikania: zapisuje akcje, symuluje plecak i HP celu."""
    def __init__(s, runy=5, efekt=True, ocr=(60, 40), geo=True):
        s.t = 0.0; s.akcje = []; s.runy = runy; s.efekt = efekt; s.ocr_wynik = ocr
        s.hp = 100; s.pamiec = {}; s.geo = geo; s.wywolan_kont = 0
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def log(s, t): LOGI.append(t)
    def kontenery(s):
        s.wywolan_kont += 1
        przed = [{"slot": 0, "id": 3147, "ilosc": 1}]
        if s.runy:
            przed.append({"slot": 1, "id": 3198, "ilosc": s.runy})
        return [{"nazwa": "Backpack", "pojemnosc": 20, "przedmioty": przed}]
    def geometria(s):
        return {"reka": {}, "plecak": [(580 + 37 * i, 581) for i in range(20)]} if s.geo else None
    def prawy(s, x, y): s.akcje.append(("prawy", x, y))
    def lewy(s, x, y): s.akcje.append(("lewy", x, y))
    def lewy_pole(s, dx, dy):
        s.akcje.append(("pole", dx, dy))
        if s.efekt and s.akcje[-2][0] == "lewy":
            s.runy -= 1
    def zrzut(s): return object()
    def ocr(s, obraz, x, y): return None if s.ocr_wynik is None else (x + s.ocr_wynik[0], y + s.ocr_wynik[1])
    def hp_celu(s, i): return s.hp
    def klawisz(s, k): s.akcje.append(("klawisz", k))

CEL = {"id": 10, "dx": 1, "dy": 0, "hp": 100}

# 1. strzel: kolejność akcji i pozycja runy (slot 1)
e = Env()
w = runa_klik.strzel(e, dict(CEL))
sprawdz("1a ok", w["wynik"] == "ok", w)
sprawdz("1b kolejność prawy -> lewy(menu) -> pole", [a[0] for a in e.akcje] == ["prawy", "lewy", "pole"], e.akcje)
sprawdz("1c prawy na slocie 1 (617,581)", e.akcje[0] == ("prawy", 617, 581), e.akcje[0])
sprawdz("1d menu z OCR (+60,+40)", e.akcje[1] == ("lewy", 677, 621), e.akcje[1])
sprawdz("1e pole celu", e.akcje[2] == ("pole", 1, 0))
sprawdz("1f offset zapamiętany", e.pamiec.get("offset") == (60, 40))

# 2. OCR zawiódł: ostatni znany offset, potem domyślny
e = Env(ocr=None); w = runa_klik.strzel(e, dict(CEL))
sprawdz("2a fallback domyślny", e.akcje[1] == ("lewy", 617 + runa_klik.MENU_DX, 581 + runa_klik.MENU_DY), e.akcje[1])
e = Env(ocr=None); e.pamiec["offset"] = (5, 9); runa_klik.strzel(e, dict(CEL))
sprawdz("2b ostatni znany offset", e.akcje[1] == ("lewy", 622, 590), e.akcje[1])

# 3. brak runy: bez żadnego kliknięcia
e = Env(runy=0); w = runa_klik.strzel(e, dict(CEL))
sprawdz("3 brak runy", w["wynik"] == "brak_runy" and not e.akcje, (w, e.akcje))

# 4. brak geometrii / slot poza oknem
e = Env(geo=False); w = runa_klik.strzel(e, dict(CEL))
sprawdz("4 brak geometrii", w["wynik"] == "brak_geometrii" and not e.akcje, w)

# 5. brak efektu: Escape i wynik bez_efektu
e = Env(efekt=False); w = runa_klik.strzel(e, dict(CEL), weryfikacja_s=1.0)
sprawdz("5 bez efektu: Escape", w["wynik"] == "bez_efektu" and e.akcje[-1] == ("klawisz", "Escape"), (w, e.akcje))

# 6. potwierdzenie przez HP celu (bez zmiany licznika)
e = Env(efekt=False)
orig = e.hp_celu
def hp_spada(i):
    e.hp = 70; return e.hp
e.hp_celu = hp_spada
w = runa_klik.strzel(e, dict(CEL))
sprawdz("6 ok po spadku HP", w["wynik"] == "ok", w)

# 7. parser TSV Use with
tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n" \
      "5\t1\t1\t1\t1\t1\t10\t8\t40\t30\t90\tUse\n5\t1\t1\t1\t1\t2\t60\t8\t70\t30\t90\twith\n" \
      "5\t1\t1\t1\t2\t1\t10\t50\t40\t30\t90\tLook\n" \
      "5\t1\t1\t1\t3\t1\t10\t90\t40\t30\t90\tUse\n5\t1\t1\t1\t3\t2\t60\t90\t60\t30\t90\twith\n"
sprawdz("7 parser TSV (pierwszy wiersz)", runa_klik.znajdz_use_with(tsv) == (70, 23), runa_klik.znajdz_use_with(tsv))
sprawdz("7b parser bez Use with", runa_klik.znajdz_use_with(tsv.replace("with", "xx")) is None)

# --- integracja z cavebotem ---------------------------------------------------------
class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.klawisze = []; s.mana = 100; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp * 1.9, "max_hp": 190, "mana": s.mana, "max_mana": 100}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
def zrob(s, env):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: ["mięso"], ile_jedzenia=lambda: None)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.runa_klik_env = env; b.uh_restore = False
    return b
def troll(x, y, hp=100, i=10): return {"id": i, "nazwa": "Troll", "gracz": False, "x": x, "y": y, "z": 7, "hp": hp}
P0 = (100, 100, 7)
cavebot.RUNA_AKTYWNA = 1; cavebot.RUNA_TRYB_KLIK = 1
def wlacz(s, b, hp=100):
    s.stwory = [troll(101, 100, hp)]
    s.t += 0.1; b.tick()
    assert b.cel is not None

# 8. strzał klikiem, bez F4
s = Swiat(); e = Env(); b = zrob(s, e); wlacz(s, b)
L = [troll(101, 100)]
b.runa_ostatni = float("-inf"); b.runa_klik_do = float("-inf")
e.akcje.clear()
sprawdz("8a obieg zużyty", b._runa_tick({}, P0, L, 100.0) is True)
sprawdz("8b klik, nie F4", [a[0] for a in e.akcje] == ["prawy", "lewy", "pole"] and "F4" not in s.klawisze, (e.akcje, s.klawisze))
sprawdz("8c log", any(l.startswith("[RUNA] strzał klik w Troll") for l in LOGI))
sprawdz("8d interwał (po 1 s nie)", b._runa_tick({}, P0, L, 101.0) is False)

# 9. brak runy: log raz, bez spamu i bez klików, sprawdzanie rzadko
s = Swiat(); e = Env(runy=0); b = zrob(s, e); wlacz(s, b); e.akcje.clear(); LOGI.clear()
L = [troll(101, 100)]; b.runa_ostatni = float("-inf")
for i in range(8):
    b._runa_tick({}, P0, L, 100.0 + 3 * i)
sprawdz("9a brak klików", not e.akcje, e.akcje)
sprawdz("9b log raz", sum("brak runy" in l for l in LOGI) == 1, [l for l in LOGI if "RUNA" in l])
sprawdz("9c odczyt plecaka rzadko (<=2 w 21 s)", e.wywolan_kont <= 2, e.wywolan_kont)

# 10. porażki -> chłodzenie
s = Swiat(); e = Env(efekt=False); b = zrob(s, e); wlacz(s, b); e.akcje.clear()
L = [troll(101, 100)]; b.runa_ostatni = float("-inf")
t = 100.0
for i in range(3):
    b._runa_tick({}, P0, L, t); t += 3.0
sprawdz("10a 3 porażki", b.runa_klik_do > t - 3.0, b.runa_klik_do)
n = len(e.akcje)
sprawdz("10b w chłodzeniu bez klików", b._runa_tick({}, P0, L, t + 10) is False and len(e.akcje) == n)
sprawdz("10c po chłodzeniu znów próba", b._runa_tick({}, P0, L, t + cavebot.RUNA_KLIK_CHLODZENIE_S + 5) is True)

# 11. UH w toku / tarcza zdjęta / ucieczka: nie strzela
for nazwa, ustaw in (("tarcza zdjęta", lambda b: setattr(b, "uh_restore", True)),
                     ("stan UH", lambda b: setattr(b, "stan", "UH")),
                     ("ucieczka", lambda b: setattr(b, "ucieczka", True))):
    s = Swiat(); e = Env(); b = zrob(s, e); wlacz(s, b); e.akcje.clear()
    b.runa_ostatni = float("-inf"); ustaw(b)
    sprawdz(f"11 {nazwa}: brak strzału", b._runa_tick({}, P0, [troll(101, 100)], 100.0) is False and not e.akcje)

# 12. cel poza zasięgiem / niewidoczny / HP poniżej progu
s = Swiat(); e = Env(); b = zrob(s, e); wlacz(s, b); e.akcje.clear(); b.runa_ostatni = float("-inf")
sprawdz("12a poza zasięgiem RUNA_ZASIEG", b._runa_tick({}, P0, [troll(110, 100)], 100.0) is False and not e.akcje)
sprawdz("12b cel nie na liście", b._runa_tick({}, P0, [], 100.0) is False and not e.akcje)
cavebot.RUNA_MIN_HP_CELU = 40
sprawdz("12c HP < RUNA_MIN_HP_CELU", b._runa_tick({}, P0, [troll(101, 100, hp=30)], 100.0) is False and not e.akcje)
cavebot.RUNA_MIN_HP_CELU = 0

# 13. tryb hotkey bez zmian, gdy RUNA_TRYB_KLIK=0
cavebot.RUNA_TRYB_KLIK = 0
s = Swiat(); e = Env(); b = zrob(s, e); wlacz(s, b); b.runa_ostatni = float("-inf"); e.akcje.clear()
b._runa_tick({}, P0, [troll(101, 100)], 100.0)
sprawdz("13 tryb 0: F4, bez klików", "F4" in s.klawisze and not e.akcje, (s.klawisze, e.akcje))
cavebot.RUNA_TRYB_KLIK = 1

# 14. pokrętła i tryby
sprawdz("14a ZAKRESY", all(k in pokretla.ZAKRESY for k in ("RUNA_TRYB_KLIK", "RUNA_ID", "RUNA_MENU_DX", "RUNA_MENU_DY",
        "RUNA_KLIK_PORAZKI", "RUNA_KLIK_CHLODZENIE_S")))
sprawdz("14b analityk nie włączy", pokretla.waliduj({"RUNA_TRYB_KLIK": 1}, {"RUNA_TRYB_KLIK": 0})[0] == {})
sprawdz("14c Pokretla widzi", "RUNA_TRYB_KLIK" in pokretla.Pokretla(cavebot, plik="/nie/ma").domyslne)
tr = json.load(open(KAT / "tryby.json"))
sprawdz("14d tryby agresywny/sredni klik", all(tr[k]["pokretla"].get("RUNA_TRYB_KLIK") == 1 and tr[k]["pokretla"]["RUNA_AKTYWNA"] == 1
        for k in ("agresywny", "sredni")))
sprawdz("14e runy: tylko runy, bez czarów jedzenia/zdrowia/ML, UH_MANA_MIN 70", tr["runy"]["pokretla"]["JEDZENIE_CZAR_AKTYWNY"] == 0
        and tr["runy"]["pokretla"]["UH_MANA_MIN"] == 70 and tr["runy"]["pokretla"]["ML_CZAR_AKTYWNY"] == 0
        and tr["runy"]["pokretla"]["ZDROWIE_CZAR_AKTYWNY"] == 0)
bl = pokretla.waliduj(tr["runy"]["pokretla"])[1]
sprawdz("14f runy waliduje bez błędów (zakresy)", not bl, bl)

# 15. jedzenie bez czaru (JEDZENIE_CZAR_AKTYWNY=0): F3 wyłączone, ML nie czeka na zapas, jedzenie z plecaka działa
cavebot.JEDZENIE_CZAR_AKTYWNY = 0
s = Swiat(); e = Env(); b = zrob(s, e)
sprawdz("15a _f3_wolny False", b._f3_wolny(100.0) is False)
sprawdz("15b ML/UH nie czekają na zapas", b._ml_czeka_na_zapas({"mana": 100}, 100.0) is False)
sprawdz("15c _uh_blokada bez 'zapas_jedzenia'", b._uh_blokada({"mana": 100, "proc": 100}, P0, 100.0) != "zapas_jedzenia")
b.jedzenie_nie_do = float("-inf"); b.hp_wzrost = 0.0
sprawdz("15d głód po HP -> jedzenie_potrzebne (z plecaka, bez czaru)",
        b.jedzenie_potrzebne({"hp": 100, "max_hp": 190, "mana": 100, "max_mana": 100}, 1000.0, P0) is True)

# 16. pojemnik na runy (Purple backpack, id 2868): runa szukana także w nim, z jego własnej siatki
class EnvRuny(Env):
    def __init__(s, w_plecaku=0, w_runach=3, geo_runy=True, **kw):
        super().__init__(runy=0, **kw)
        s.w_plecaku, s.w_runach, s.geo_runy = w_plecaku, w_runach, geo_runy
    def kontenery(s):
        pl = [{"slot": 0, "id": 3147, "ilosc": 1}] + ([{"slot": 1, "id": 3198, "ilosc": s.w_plecaku}] if s.w_plecaku else [])
        pr = [{"slot": 0, "id": 3147, "ilosc": 1}] + ([{"slot": 5, "id": 3198, "ilosc": s.w_runach}] if s.w_runach else [])
        return [{"numer": 0, "nazwa": "purple backpack", "id": 2868, "pojemnosc": 20, "przedmioty": pr},
                {"numer": 1, "nazwa": "backpack", "id": 2854, "pojemnosc": 20, "przedmioty": pl}]
    def geometria(s):
        g = {"reka": {}, "plecak": [(580 + 37 * i, 581) for i in range(20)]}
        if s.geo_runy:
            g["runy"] = [(580 + 37 * (i % 4), 781 + 37 * (i // 4)) for i in range(20)]
        return g
    def lewy_pole(s, dx, dy):
        s.akcje.append(("pole", dx, dy))
        if s.efekt and s.akcje[-2][0] == "lewy":
            if s.w_runach:
                s.w_runach -= 1
            else:
                s.w_plecaku -= 1

e = EnvRuny(); w = runa_klik.strzel(e, dict(CEL))
sprawdz("16a runa tylko w pojemniku: strzał z jego siatki (slot 5 -> (617, 818))", w["wynik"] == "ok"
        and e.akcje[0] == ("prawy", 617, 818), (w, e.akcje))
e = EnvRuny(w_plecaku=2, w_runach=0); w = runa_klik.strzel(e, dict(CEL))
sprawdz("16b runa tylko w plecaku (dwa okna): siatka plecaka, slot 1", w["wynik"] == "ok" and e.akcje[0] == ("prawy", 617, 581), (w, e.akcje))
e = EnvRuny(w_plecaku=2, w_runach=0, geo_runy=False); w = runa_klik.strzel(e, dict(CEL))
sprawdz("16c pojemnik bez siatki, runa w plecaku: działa", w["wynik"] == "ok" and e.akcje[0] == ("prawy", 617, 581), (w, e.akcje))
e = EnvRuny(w_plecaku=0, w_runach=2, geo_runy=False); w = runa_klik.strzel(e, dict(CEL))
sprawdz("16d runa w pojemniku bez jego siatki: brak_geometrii, zero klików", w["wynik"] == "brak_geometrii" and not e.akcje, (w, e.akcje))
e = EnvRuny(w_plecaku=0, w_runach=0); w = runa_klik.strzel(e, dict(CEL))
sprawdz("16e brak runy w obu", w["wynik"] == "brak_runy" and not e.akcje, w)
e = EnvRuny(w_plecaku=1, w_runach=1); w = runa_klik.strzel(e, dict(CEL))
sprawdz("16f licznik łączny (ubyło z pojemnika)", w["wynik"] == "ok", w)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
