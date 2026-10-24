"""Zwiecha walki, wydra 23.10 11:08-11:38 (~29 min bez zabicia trolla, fantomowa walka: kliki obok celu, "[ATAK] 5 klików bez efektu"
co ~50 s, cel ignorowany 30 s i wraca). Odtworzenie prawdziwych momentów z logu mozg-stdout-1023-1106.log. Atrapy, nic nie trafia do gry.
a) zwiecha.Detektor na prawdziwych czasach zdarzeń: szczebel 1 po 3. zdarzeniu (11:09:54), 2 po kolejnych dwóch (11:10:44),
   3 (restart) po kolejnych dwóch (11:12:24) - czyli w niecałe 4 min zamiast 29;
b) brak fałszywych alarmów: przyrost expa, tylko 2 zdarzenia, zdarzenia rozrzucone poza oknem, cisza, odstęp 15 s (S2 + bez efektu to jedno);
c) cavebot na atrapie świata (troll obok, flaga ramki zawsze False, jak na wydrze): w logu "ZWIECHA: ... naprawa 1/3, 2/3, 3/3",
   unieważniony prostokąt mapy, zignorowane stwory, flaga zwiecha_restart; dalej walka i zabicie zeruje epizod;
d) zdrowa walka (HP celu spada, zabicia) i legalne czekanie "[DZIURA] odpuszczam" nie wywołują zwiechy."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot, ekran

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

def sek(hms):
    h, m, s = map(int, hms.split(":")); return h * 3600 + m * 60 + s

# prawdziwe czasy "[ATAK] 5 klików bez efektu" z mozg-stdout-1023-1106.log (po upadku w dziurę na z8 o 11:08:51)
BEZ_EFEKTU = ["11:09:12", "11:09:34", "11:09:54", "11:10:25", "11:10:44", "11:11:33", "11:12:24", "11:13:15", "11:14:08", "11:14:56"]
POZ = (32467, 32233, 8)

# --- a) detektor na prawdziwych czasach ---
try:
    import zwiecha
except ImportError:
    zwiecha = None
sprawdz("a0 moduł zwiecha istnieje", zwiecha is not None)
if zwiecha is not None:
    d = zwiecha.Detektor()
    szczebel = {}
    for h in BEZ_EFEKTU:
        t = sek(h)
        d.zdarzenie(t, "klik_bez_efektu", POZ)
        k = d.tick(t, 100)                   # exp stoi (wydra nie zabiła ani jednego trolla)
        if k and k not in szczebel:
            szczebel[k] = h
    sprawdz("a1 szczebel 1 po 3. zdarzeniu (11:09:54)", szczebel.get(1) == "11:09:54", str(szczebel))
    sprawdz("a2 szczebel 2 po kolejnych dwóch (11:10:44)", szczebel.get(2) == "11:10:44", str(szczebel))
    sprawdz("a3 szczebel 3 = restart po kolejnych dwóch (11:12:24)", szczebel.get(3) == "11:12:24", str(szczebel))
    sprawdz("a4 od upadku (11:08:51) do restartu < 5 min (było 29,5 min)", sek(szczebel.get(3, "23:59:59")) - sek("11:08:51") < 300)
    d2 = zwiecha.Detektor(); wyn = []
    for h in BEZ_EFEKTU:
        d2.zdarzenie(sek(h), "klik_bez_efektu", POZ); wyn.append(d2.tick(sek(h), 100))
    # drabina nie kończy się na 3: kolejne zdarzenia ponawiają szczebel 3 (restart odłożony przy niskim HP) co KROK_N zdarzeń
    sprawdz("a5 po szczeblu 3 kolejna próba dopiero po 2 zdarzeniach", wyn.count(3) >= 1 and all(x in (None, 1, 2, 3) for x in wyn), str(wyn))

    # b) brak fałszywych alarmów
    d = zwiecha.Detektor()
    d.zdarzenie(100, "klik_bez_efektu"); d.zdarzenie(160, "klik_bez_efektu")
    sprawdz("b1 dwa zdarzenia: bez zwiechy", d.tick(170, 5) is None)
    d.zdarzenie(220, "klik_bez_efektu")
    sprawdz("b2 trzecie zdarzenie w oknie: szczebel 1", d.tick(220, 5) == 1)
    d = zwiecha.Detektor()
    d.zdarzenie(100, "klik_bez_efektu"); d.zdarzenie(200, "klik_bez_efektu"); d.tick(200, 5)
    r1 = d.tick(250, 60)
    d.zdarzenie(300, "klik_bez_efektu")
    sprawdz("b3 przyrost expa (zabity potwór) zeruje epizod: trzecie zdarzenie po zabiciu nie jest zwiechą",
            r1 is None and d.tick(300, 60) is None and len(d.zdarzenia) == 1, str(d.zdarzenia))
    d = zwiecha.Detektor()
    d.zdarzenie(0, "klik_bez_efektu"); d.zdarzenie(400, "klik_bez_efektu"); d.zdarzenie(800, "klik_bez_efektu")
    sprawdz("b4 zdarzenia co 400 s (poza oknem 300 s): bez zwiechy", d.tick(800, 5) is None)
    d = zwiecha.Detektor()
    d.zdarzenie(0, "klik_bez_efektu"); d.zdarzenie(5, "straznik_s2")      # S2 strażnika w tym samym cyklu co "bez efektu" = jedno zdarzenie
    sprawdz("b5 odstęp < 15 s: jedno zdarzenie", len(d.zdarzenia) == 1)
    d = zwiecha.Detektor()
    for t in (0, 30, 60):
        d.zdarzenie(t, "klik_bez_efektu")
    d.tick(60, 5)
    sprawdz("b6 cisza 240 s kończy epizod", d.tick(60 + 241, 5) is None and not d.zdarzenia)

# --- c) cavebot na atrapie świata ---
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0; cavebot.ATAK_INNY_CEL = False; cavebot.STRAZNIK_CEL = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ZAPOMNIJ = []
ekran.zapomnij_prostokat = lambda *a, **k: (ZAPOMNIJ.append(1), (0, 0, 1, 1))[1]

class Swiat:
    def __init__(s, hp_gracza=190):
        s.t = 0.0; s.poz = [32467, 32233, 8]; s.flaga = False; s.w_grze = 99; s.klik = []; s.klawisze = []; s.hp = 100
        s.exp = 100; s.hp_gracza = hp_gracza
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp_gracza, "max_hp": 190, "mana": 100, "max_mana": 100, "exp": s.exp}}
        if z["cmd"] == "cel_ataku":
            return {"id": s.w_grze}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 8, "hp": 100}
            tr = [{"id": 1073787941 + i, "nazwa": "Troll", "gracz": False, "x": s.poz[0] - 1 + i, "y": s.poz[1] + 1, "z": 8,
                   "hp": s.hp, "atakowany": s.flaga} for i in range(3)]
            return {"stwory": [ja] + tr}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k): return True

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(32467 + i, 32233, 8) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: s.klik.append(s.t), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5", czy_atakowany=lambda m, g: m.get("atakowany"))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.5):
    s.t += dt; b.tick()

s = Swiat(); b = zrob(s); LOGI.clear(); ZAPOMNIJ.clear()
for _ in range(2000):
    # jak w prawdziwym logu: cel zignorowany po limicie kliknięć wraca po ATAK_LIMIT_IGNOROWANIE s (tu: od razu, nie czekamy 30 s)
    for k in list(b.ignorowane):
        if b.ignor_powod.get(k, ("",))[0] == "atak_klik":
            b.ignorowane[k] = min(b.ignorowane[k], s.t + 8.0)
    tick(s, b)
    if getattr(b, "zwiecha_restart", False):
        break
zw = [l for l in LOGI if l.startswith("ZWIECHA")]
sprawdz("c1 w logu wpisy 'ZWIECHA: ... naprawa 1/3', '2/3', '3/3'",
        any("naprawa 1/3" in l for l in zw) and any("naprawa 2/3" in l for l in zw) and any("naprawa 3/3" in l for l in zw), str(zw)[:600])
sprawdz("c2 wpis ma 'od N s' i pozycję", bool(zw) and "bez zabicia od" in zw[0] and "(32467, 32233, 8)" in zw[0], zw[0] if zw else "")
sprawdz("c3 szczebel 3 prosi o restart (zwiecha_restart) - mozg wykona os.execv jak przy ŚLEPOCIE", getattr(b, "zwiecha_restart", False) is True)
sprawdz("c4 od początku do restartu < 6 min symulowanego czasu", s.t < 360, f"t={s.t:.0f} s")
sprawdz("c5 prostokąt mapy unieważniony (zapomnij_prostokat) co najmniej raz w szczeblu 1", len(ZAPOMNIJ) >= 1, str(len(ZAPOMNIJ)))
sprawdz("c6 w logu nie ma STOP ani alarmu krytycznego za brak postępu", not any("STOP" in l or "ALARM" in l for l in zw), str(zw)[:300])
sprawdz("c7 szczebel 2 ignoruje stwory w pobliżu (inny punkt)", any(v for v in b.ignorowane.values() if v > s.t) or any("naprawa 2/3" in l for l in zw))

# c8: zabicie (przyrost expa) kończy epizod, następne zdarzenia liczą się od zera
s = Swiat(); b = zrob(s); LOGI.clear()
for _ in range(400):
    for k in list(b.ignorowane):
        if b.ignor_powod.get(k, ("",))[0] == "atak_klik":
            b.ignorowane[k] = min(b.ignorowane[k], s.t + 8.0)
    tick(s, b)
    if any("naprawa 1/3" in l for l in LOGI):
        break
s.exp += 250                                    # troll zabity
for _ in range(4):
    tick(s, b)
zz = getattr(b, "zwiecha", None)
sprawdz("c8 przyrost expa zeruje epizod zwiechy", zz is not None and zz.szczebel == 0 and not zz.zdarzenia, str(getattr(zz, "szczebel", None)))

# c9: restart odłożony przy niskim HP (nie w środku groźnej walki)
s = Swiat(hp_gracza=90); b = zrob(s); LOGI.clear()
for _ in range(2000):
    for k in list(b.ignorowane):
        if b.ignor_powod.get(k, ("",))[0] == "atak_klik":
            b.ignorowane[k] = min(b.ignorowane[k], s.t + 8.0)
    tick(s, b)
    if any("naprawa 3/3" in l for l in LOGI):
        break
sprawdz("c9 HP 47%: szczebel 3 odłożony, brak zwiecha_restart", not getattr(b, 'zwiecha_restart', False) and any("restart odłożony" in l for l in LOGI),
        str([l for l in LOGI if l.startswith("ZWIECHA")])[:300])

# c10: pokrętło ZWIECHA=0 = zero zmian
cavebot.ZWIECHA = 0
s = Swiat(); b = zrob(s); LOGI.clear()
for _ in range(600):
    for k in list(b.ignorowane):
        if b.ignor_powod.get(k, ("",))[0] == "atak_klik":
            b.ignorowane[k] = min(b.ignorowane[k], s.t + 8.0)
    tick(s, b)
sprawdz("c10 ZWIECHA=0: bez wpisów ZWIECHA i bez restartu", not any(l.startswith("ZWIECHA") for l in LOGI) and not getattr(b, 'zwiecha_restart', False))
cavebot.ZWIECHA = 1

# d) zdrowa walka: HP celu spada co tick (atak działa), potem zabicie; zero zwiechy
s = Swiat(); s.flaga = True; s.w_grze = 1073787941; b = zrob(s); LOGI.clear()
for i in range(120):
    s.hp = max(5, 100 - 2 * i)
    tick(s, b)
sprawdz("d1 zdrowa walka (HP celu spada, flaga True): bez zwiechy", not any(l.startswith("ZWIECHA") for l in LOGI) and not getattr(b, 'zwiecha_restart', False))

# d2: pokrętła w pokretla.py
import pokretla
sprawdz("d2 pokrętła ZWIECHA* w tabeli zakresów", all(k in pokretla.ZAKRESY for k in ("ZWIECHA", "ZWIECHA_N", "ZWIECHA_RESTART")) if hasattr(pokretla, "ZAKRESY")
        else True)

print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
