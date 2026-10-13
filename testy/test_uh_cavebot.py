"""Integracja uh.py z cavebotem (UH_AKTYWNY): na atrapach, bez X11 i bez prawdziwych klików (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla, uh

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
cavebot.ML_CZAR_OPOZNIENIE = (0.0, 0.0); cavebot.ML_CZAR_DLUGA_SZANSA = 0.0
cavebot.ML_CZAR_ZAPAS_MANY = (0, 0); cavebot.ML_CZAR_EXTRA_PRZERWA = (0.0, 0.0)
TMP = Path(tempfile.mkdtemp())
cavebot.UH_STAN_PLIK = TMP / "uh_stan.json"
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.klawisze = []; s.mana = 125; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp * 1.9, "max_hp": 190, "mana": s.mana, "max_mana": 125}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        return {}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

ALARMY = []
def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: ["mięso"], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: ALARMY.append(w), spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.jz_odczyt = (0.0, 10)
    return b

def tick(s, b, n=1):
    for _ in range(n):
        s.t += 0.1
        b.tick()

WYWOLANIA = []
WYNIKI = []
def fake_zrob(env, *a, **k):
    WYWOLANIA.append(("zrob", uh.UH_KLAWISZ, uh.UH_KOSZT, uh.UH_CZAR))
    r = WYNIKI.pop(0) if WYNIKI else {"wynik": "ok", "powod": "ok", "alarm": False, "czas_s": 5.0, "rzuty": 1}
    return r
def fake_przywroc(env, *a, **k):
    WYWOLANIA.append(("przywroc",))
    env.stan.pop("tarcza_id", None)
    return {"wynik": "ok", "powod": "ok", "alarm": False, "czas_s": 1.0, "rzuty": 0}
uh.zrob_runa = fake_zrob; uh.przywroc = fake_przywroc
def reset():
    WYWOLANIA.clear(); WYNIKI.clear(); ALARMY.clear()
    if cavebot.UH_STAN_PLIK.exists(): cavebot.UH_STAN_PLIK.unlink()
    cavebot.UH_AKTYWNY = 0; cavebot.ML_CZAR_AKTYWNY = 0

# 0. kontrakt
sprawdz("0a domyślnie", cavebot.UH_AKTYWNY == 0 and cavebot.UH_KLAWISZ == "F6" and cavebot.UH_CZAR == "adori gran"
        and cavebot.UH_KOSZT == 70 and cavebot.UH_MANA_MIN == 95 and cavebot.UH_MIN_HP == 90 and cavebot.UH_ODSTEP_S == 20.0)
sprawdz("0b zakresy", all(k in pokretla.ZAKRESY for k in ("UH_AKTYWNY", "UH_KOSZT", "UH_MANA_MIN", "UH_MIN_HP", "UH_ODSTEP_S", "UH_MOB_DYSTANS")))
sprawdz("0b2 UH_MOB_DYSTANS", cavebot.UH_MOB_DYSTANS == 3 and pokretla.ZAKRESY["UH_MOB_DYSTANS"] == (1, 10)
        and pokretla.waliduj({"UH_MOB_DYSTANS": 2}, {"UH_MOB_DYSTANS": 3})[0] == {}
        and pokretla.waliduj({"UH_MOB_DYSTANS": 5}, {"UH_MOB_DYSTANS": 3})[0] == {"UH_MOB_DYSTANS": 5}
        and json.loads((Path(cavebot.__file__).parent / "tryby.json").read_text())["runy"]["pokretla"]["UH_MOB_DYSTANS"] == 3)
sprawdz("0c Karol może włączyć", pokretla.waliduj({"UH_AKTYWNY": 1, "UH_KLAWISZ": "F6"})[0] == {"UH_AKTYWNY": 1, "UH_KLAWISZ": "F6"})
sprawdz("0d analityk nie włączy", pokretla.waliduj({"UH_AKTYWNY": 1}, {"UH_AKTYWNY": 0})[0] == {}
        and pokretla.waliduj({"UH_MIN_HP": 70}, {"UH_MIN_HP": 90})[0] == {})
sprawdz("0e Pokretla widzi", "UH_AKTYWNY" in pokretla.Pokretla(cavebot, plik="/nie/ma").domyslne)
pk = pokretla.Pokretla(cavebot, plik=TMP / "nz.json", log=lambda t: None)
(TMP / "nz.json").write_text(json.dumps({"UH_AKTYWNY": 1})); pk.odswiez()
sprawdz("0f na_zywo włącza", cavebot.UH_AKTYWNY == 1)
(TMP / "nz.json").write_text("{}"); pk.mtime = None; pk.odswiez()
sprawdz("0g powrót do 0", cavebot.UH_AKTYWNY == 0)

# 1. wyłączone: bez wywołania
reset(); s = Swiat(); b = zrob(s); tick(s, b, 5)
sprawdz("1 wyłączone", not WYWOLANIA, WYWOLANIA)

# 2. włączone, spokój, mana 125: robi runę, ustawia klawisz/koszt
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s); tick(s, b, 3)
sprawdz("2a rzut", len(WYWOLANIA) == 1 and WYWOLANIA[0] == ("zrob", "F6", 70, "adori gran"), WYWOLANIA)
sprawdz("2b odstęp 20 s", (tick(s, b, 3), len(WYWOLANIA))[1] == 1)
s.t += 25; tick(s, b, 1)
sprawdz("2c po odstępie kolejna", len(WYWOLANIA) == 2, WYWOLANIA)
sprawdz("2d log", any(l.startswith("[UH] start") for l in LOGI) and any("[UH] wynik ok" in l for l in LOGI))

# 3. szczur w widoku / cel: nie startuje
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); s.stwory = [{"id": 9, "nazwa": "Rat", "gracz": False, "x": 102, "y": 100, "z": 7, "hp": 100}]
b = zrob(s); b.cel = None
g = s.zapytaj({"cmd": "gracz"})["gracz"]; g["proc"] = 100.0
sprawdz("3a szczur w widoku", b._uh_tick(g, (100, 100, 7), s.zapytaj({"cmd": "stwory"})["stwory"], 50.0) is False and not WYWOLANIA)
s.stwory = [{"id": 9, "nazwa": "Rat", "gracz": False, "x": 105, "y": 100, "z": 8, "hp": 100}]
sprawdz("3b szczur na innym piętrze nie blokuje", b._uh_tick(g, (100, 100, 7), s.zapytaj({"cmd": "stwory"})["stwory"], 50.0) is True)
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s); b.cel = {"id": 9}
sprawdz("3c walka (cel)", b._uh_tick(g, (100, 100, 7), [], 50.0) is False and not WYWOLANIA)
b.cel = None; b.ucieczka = True
sprawdz("3d ucieczka", b._uh_tick(g, (100, 100, 7), [], 50.0) is False and not WYWOLANIA)
b.ucieczka = False; b.w_lootcie = True
sprawdz("3e loot", b._uh_tick(g, (100, 100, 7), [], 50.0) is False and not WYWOLANIA)
b.w_lootcie = False
sprawdz("3f HP 80% < 90", b._uh_tick(dict(g, proc=80.0), (100, 100, 7), [], 50.0) is False and not WYWOLANIA)

# 4. mana: < 95 nie; ML czeka na manę (hold), po UH_HOLD_MAX_S rzuca
reset(); cavebot.UH_AKTYWNY = 1; cavebot.ML_CZAR_AKTYWNY = 1
s = Swiat(); s.mana = 60; b = zrob(s); tick(s, b, 4)
sprawdz("4a mana 60: UH nie, ML czeka", not WYWOLANIA and not s.klawisze, s.klawisze)
s.t += cavebot.UH_HOLD_MAX_S + 10; b.mana_wzrost = b.mana_rosla = s.t; tick(s, b, 4)
sprawdz("4b po UH_HOLD_MAX_S ML rzuca", "F1" in s.klawisze, s.klawisze)
reset(); cavebot.UH_AKTYWNY = 0; cavebot.ML_CZAR_AKTYWNY = 1
s = Swiat(); s.mana = 60; b = zrob(s); tick(s, b, 3)
sprawdz("4c UH wyłączone: ML jak dotąd", "F1" in s.klawisze, s.klawisze)
reset(); cavebot.UH_AKTYWNY = 1; cavebot.ML_CZAR_AKTYWNY = 1
s = Swiat(); s.mana = 125; b = zrob(s); tick(s, b, 3)
sprawdz("4d mana 125: UH przed ML", len(WYWOLANIA) == 1 and "F1" not in s.klawisze, (WYWOLANIA, s.klawisze))
cavebot.ML_CZAR_AKTYWNY = 0

# 5. porażki, alarm, brak_blank
P_ = {"wynik": "przerwane", "powod": "nie wyszło", "alarm": False, "czas_s": 2.0, "rzuty": 0}
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s)
g = s.zapytaj({"cmd": "gracz"})["gracz"]; g["proc"] = 100.0
for i in range(3):
    WYNIKI.append(dict(P_)); b.uh_ostatni = float("-inf"); b.czar_ostatni = float("-inf")
    b._uh_tick(g, (100, 100, 7), [], 100.0 + i)
sprawdz("5a 3 porażki wyłączają na 30 min", b.uh_wylaczony_do - b.zegar() > 1700 and len(WYWOLANIA) == 3, b.uh_wylaczony_do)
b.uh_ostatni = float("-inf")
sprawdz("5b wyłączony", b._uh_tick(g, (100, 100, 7), [], 101.0) is False and len(WYWOLANIA) == 3)
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s)
WYNIKI.append({"wynik": "przerwane", "powod": "tarcza poza slotem", "alarm": True, "czas_s": 9.0, "rzuty": 0})
b._uh_tick(g, (100, 100, 7), [], 100.0)
sprawdz("5c alarm: wyłączenie 30 min i alarm", b.uh_wylaczony_do - b.zegar() > 1700 and any("UH:" in a for a in ALARMY), ALARMY)
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s)
WYNIKI.append({"wynik": "brak_blank", "powod": "brak", "alarm": False, "czas_s": 0.5, "rzuty": 0})
b._uh_tick(g, (100, 100, 7), [], 100.0)
sprawdz("5d brak_blank 10 min", 590 < b.uh_wylaczony_do - b.zegar() < 610, b.uh_wylaczony_do)
# przerwanie z callbacku (stwór) nie jest porażką
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s)
def zrob_przerw(env, *a, **k):
    s.stwory = [{"id": 9, "nazwa": "Rat", "gracz": False, "x": 102, "y": 100, "z": 7, "hp": 100}]
    r = env.przerwanie()
    return {"wynik": "przerwane", "powod": r, "alarm": False, "czas_s": 1.0, "rzuty": 0}
uh.zrob_runa = zrob_przerw
b._uh_tick(g, (100, 100, 7), [], 100.0)
sprawdz("5e przerwanie stworem: bez porażki", b.uh_porazki == 0 and b.uh_przerwal_cavebot and "Rat" in b.uh_przerwal_cavebot,
        (b.uh_porazki, b.uh_przerwal_cavebot))
s.stwory = []; s.hp = 70
sprawdz("5f HP < 80 przerywa", "HP" in (b._uh_przerwanie() or ""), b._uh_przerwanie())
s.hp = 100; b.ucieczka = True
sprawdz("5g ucieczka przerywa", b._uh_przerwanie() == "ucieczka")
b.ucieczka = False
sprawdz("5h spokój: brak przerwania", b._uh_przerwanie() is None)
uh.zrob_runa = fake_zrob

# 6. restore po restarcie (stan w pliku), także przy UH_AKTYWNY=0
reset(); cavebot.UH_STAN_PLIK.write_text(json.dumps({"tarcza_id": 3426}))
s = Swiat(); s.mana = 10; b = zrob(s); b.zd_oczekuje = None
tick(s, b, 2)
sprawdz("6a przywrócenie tarczy", WYWOLANIA[:1] == [("przywroc",)] and not cavebot.UH_STAN_PLIK.exists(), (WYWOLANIA, cavebot.UH_STAN_PLIK.exists()))
tick(s, b, 3)
sprawdz("6b potem już nie", len(WYWOLANIA) == 1)
# stan trwały: zapis i usunięcie
st = cavebot._UhStan(cavebot.UH_STAN_PLIK); st["tarcza_id"] = 1
sprawdz("6c zapis", json.loads(cavebot.UH_STAN_PLIK.read_text()) == {"tarcza_id": 1})
st.pop("tarcza_id", None)
sprawdz("6d usunięcie", not cavebot.UH_STAN_PLIK.exists())

# 7. UH_MOB_DYSTANS: szczur dalej niż 3 pola nie blokuje, bliżej tak; gracz zawsze w pełnym widoku
def mob(x, y=100, **k): return dict({"id": 9, "nazwa": "Rat", "gracz": False, "x": x, "y": y, "z": 7, "hp": 100}, **k)
def start(stwory, cel=None, stan=None):
    reset(); cavebot.UH_AKTYWNY = 1
    s = Swiat(); s.stwory = stwory; b = zrob(s); b.cel = cel
    if stan: b.stan = stan
    g = s.zapytaj({"cmd": "gracz"})["gracz"]; g["proc"] = 100.0
    return s, b, b._uh_tick(g, (100, 100, 7), s.zapytaj({"cmd": "stwory"})["stwory"], 50.0)
sprawdz("7a szczur na 5 polach nie blokuje", start([mob(105)])[2] is True and len(WYWOLANIA) == 1)
sprawdz("7b szczur na 2 polach blokuje", start([mob(102)])[2] is False and not WYWOLANIA)
sprawdz("7c szczur na 3 polach blokuje (<=)", start([mob(103)])[2] is False)
sprawdz("7d szczur ukośnie 4,1 nie blokuje (Chebyshev 4)", start([mob(104, 101)])[2] is True)
sprawdz("7e gracz na 6 polach blokuje", start([mob(106, gracz=True, nazwa="Obcy")])[2] is False and not WYWOLANIA)
sprawdz("7f gracz na 6 polach + szczur daleko: blokuje", start([mob(106, gracz=True, nazwa="Obcy", id=5), mob(105)])[2] is False)
sprawdz("7g cel na 5 polach nie blokuje (stan WALKA, szczur w widoku)", start([mob(105)], cel={"id": 9}, stan="WALKA")[2] is True)
sprawdz("7h cel na 2 polach blokuje", start([mob(102)], cel={"id": 9}, stan="WALKA")[2] is False and not WYWOLANIA)
sprawdz("7i stary stan WALKA bez celu daleko nie blokuje", start([mob(106)], stan="WALKA")[2] is True)
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s); b.pamiec = {"cel": {"id": 9}}
sprawdz("7j pościg na pamięć blokuje", b._uh_blokada({"proc": 100.0}, (100, 100, 7), 50.0, []) == "walka")
cavebot.UH_MOB_DYSTANS = 6
sprawdz("7k dystans 6: szczur na 5 blokuje", start([mob(105)])[2] is False)
cavebot.UH_MOB_DYSTANS = 3
# callback w trakcie robienia runy
reset(); s = Swiat(); b = zrob(s); s.stwory = [mob(105)]
sprawdz("7l callback: szczur na 5 nie przerywa", b._uh_przerwanie() is None)
s.stwory = [mob(103)]
sprawdz("7m callback: szczur zbliżył się na 3 przerywa", "Rat" in (b._uh_przerwanie() or ""))
s.stwory = [mob(106, gracz=True, nazwa="Obcy")]
sprawdz("7n callback: gracz na 6 przerywa", "Obcy" in (b._uh_przerwanie() or ""))
s.stwory = [mob(106, hp=0)]
sprawdz("7o callback: martwy daleko nie przerywa", b._uh_przerwanie() is None)

import shutil; shutil.rmtree(TMP, ignore_errors=True)
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
