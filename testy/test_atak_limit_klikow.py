"""Limit kliknięć ramka_false (pętla ataku 13.10) i wybór własnego wpisu przy widmie postaci. Atrapy, bez X11."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.flaga = False; s.w_grze = 99; s.klik = []; s.klawisze = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 190, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "cel_ataku":
            return {"id": s.w_grze}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 7, "hp": 100}
            m = {"id": 1234510, "nazwa": "Troll", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}
            if s.flaga is not None:
                m["atakowany"] = s.flaga
            return {"stwory": [ja, m]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: s.klik.append(s.t), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5", czy_atakowany=lambda m, g: m.get("atakowany"))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.1):
    s.t += dt; b.tick()


cavebot.ATAK_INNY_CEL = False
cavebot.STRAZNIK_CEL = 0      # strażnik celu (P2a) ma własny test; tu mierzymy sam limit kliknięć
s = Swiat(); s.flaga = False; s.w_grze = 99
b = zrob(s)
for _ in range(60):
    tick(s, b, 0.5)
    if "Escape" in s.klawisze:
        break
sprawdz("klików przed ignorowaniem <= limit+1", len(s.klik) <= cavebot.ATAK_LIMIT_KLIKOW + 1, f"kliki={len(s.klik)}")
sprawdz("Escape po limicie", "Escape" in s.klawisze, str(s.klawisze))
sprawdz("log o limicie", any("klików bez efektu" in l for l in LOGI))
sprawdz("cel ignorowany", 1234510 in b.ignorowane)

# flaga True: licznik się nie nalicza
s = Swiat(); s.flaga = True; s.w_grze = 1234510
b = zrob(s)
for _ in range(30):
    tick(s, b, 0.5)
sprawdz("flaga True: bez Escape", "Escape" not in s.klawisze)

# widmo: dwa wpisy gracza, żywy najbliżej bloku statystyk
G = {"hp": 200, "max_hp": 200, "adres": "0x13271e68"}
stary = {"id": 268852462, "adres": "0x1169ca88", "hp": 100, "x": 32488, "y": 32294, "z": 8}
zywy = {"id": 268478551, "adres": "0x132719f8", "hp": 100, "x": 32490, "y": 32294, "z": 8}
# 19.10 (logi Mastafiana): przy równym HP rozstrzyga NAJWYŻSZE id; wpis `stary` ma tu WYŻSZE id, więc jest teraz wybierany.
# Oczekiwanie odwrócono ŚWIADOMIE względem fixtury z incydentu 13.10 (Jointoramix: żywy 268478551, widmo 268852462) - to
# kontrprzykład heurystyki id (patrz bot._wybierz_wlasny); ruch wpisu i tak wygrywa pierwszy. Adres bloku tylko bez id.
sprawdz("wybierz_wlasny: najwyższe id", bot.wybierz_wlasny([stary, zywy], G)["id"] == 268852462)
sprawdz("wybierz_wlasny: adres bloku (bez id)", bot.wybierz_wlasny([dict(stary, id=None), dict(zywy, id=None)], G)["adres"] == zywy["adres"])
G2 = {"hp": 150, "max_hp": 200, "adres": "0x13271e68"}
zywy2 = dict(zywy, hp=75); stary2 = dict(stary, hp=100)
sprawdz("wybierz_wlasny: zgodne HP", bot.wybierz_wlasny([stary2, zywy2], G2)["id"] == 268478551)
sprawdz("wybierz_wlasny: pojedynczy -> None", bot.wybierz_wlasny([stary], G) is None)

def falszywy(z):
    c = z["cmd"]
    if c == "stwory": return {"stwory": [dict(stary, gracz=True, nazwa="Ja"), dict(zywy, gracz=True, nazwa="Ja")]}
    if c == "gracz": return {"gracz": G}
    if c == "pozycja": return {"pozycja": {"x": 32488, "y": 32294, "z": 8}}
    if c == "stwor": return {"stwor": {"id": z["id"], "x": 32491, "y": 32292, "z": 8, "hp": 100}}
    raise AssertionError(c)
bot._zapytaj_surowe = falszywy
bot._wlasny.update(nazwa=None, t=float("-inf"), wpis=None)
o = bot.zapytaj({"cmd": "pozycja", "nazwa": "Ja"})
sprawdz("zapytaj pozycja z wpisu o najwyższym id (żywego)", o["pozycja"] == {"x": 32491, "y": 32292, "z": 8}, str(o))
print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
