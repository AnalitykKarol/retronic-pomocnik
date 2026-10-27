#!/usr/bin/env python3
"""25.10 (zgon Geblish 11:16): TRYB_OBRONNY. Zamiast ucieczki z progu HP bot bije to, co go bije (także stwór spoza --potwory i gracz
Z CZASZKĄ), leczy się w walce (runa leczenia z plecaka -> robienie jej -> exura -> dopiero ucieczka), a gdy kroki ucieczki stoją
przez moba, bije blokującego. Rezerwa many UH_REZERWA_LECZ w spokoju. Domyślnie TRYB_OBRONNY=0 = stare zachowanie.
Na atrapach, bez gry, X11, klików i prawdziwych plików instancji (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot  # noqa: E402,F401
import cavebot  # noqa: E402
import pokretla  # noqa: E402
import runa_klik  # noqa: E402
import tryb_obronny  # noqa: E402
import uh  # noqa: E402

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
cavebot.ML_CZAR_OPOZNIENIE = (0.0, 0.0); cavebot.ML_CZAR_DLUGA_SZANSA = 0.0
cavebot.ML_CZAR_ZAPAS_MANY = (0, 0); cavebot.ML_CZAR_EXTRA_PRZERWA = (0.0, 0.0)
cavebot.STRAZNIK_CEL = 0
TMP = Path(tempfile.mkdtemp())
cavebot.UH_STAN_PLIK = TMP / "uh_stan.json"
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []


def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


Z = 7
BLANK, UH_ID, HMM_ID = uh.UH_BLANK_ID, 3160, 3198
DOMYSLNE = {k: getattr(cavebot, k) for k in (
    "TRYB_OBRONNY", "ZDROWIE_CZAR_AKTYWNY", "RUNA_AKTYWNA", "UH_AKTYWNY", "UH_CZAR", "UH_KLAWISZ", "UH_KOSZT", "UH_MANA_MIN",
    "UH_LECZ_CZAR", "UH_LECZ_KLAWISZ", "UH_LECZ_KOSZT", "UH_REZERWA_LECZ", "OBRONA_PK_ODL", "RUNA_TRYB_KLIK")}


class Swiat:
    """hp w %, max_hp 190. Wrogowie obok (<= 1 pole) zdejmują `dmg` pp na obieg; exura (F2): +10 pp, -25 many."""
    def __init__(s, hp=70.0, mana=100, max_mana=185, dmg=3.0):
        s.t = 0.0; s.poz = [100, 100, Z]; s.stwory = []; s.klawisze = []
        s.hp = hp; s.mana = mana; s.max_mana = max_mana; s.dmg = dmg; s.blok = True

    def zegar(s): return s.t
    def spij(s, d): s.t += d

    def obok(s):
        return [m for m in s.stwory if m.get("hp", 100) > 0 and max(abs(m["x"] - s.poz[0]), abs(m["y"] - s.poz[1])) <= 1]

    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp * 1.9, "max_hp": 190, "mana": s.mana, "max_mana": s.max_mana}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": Z, "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        return {}


class P:
    nazwa = "Ja"

    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)
        if k == "F2" and p.s.mana >= 25:                     # exura
            p.s.mana -= 25; p.s.hp = min(100.0, p.s.hp + 10.0)

    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        n = (p.s.poz[0] + d[0], p.s.poz[1] + d[1])
        if p.s.blok and any((m["x"], m["y"]) == n for m in p.s.stwory):
            return tuple(p.s.poz)                           # mob na polu kroku: nie ruszamy
        p.s.poz[0], p.s.poz[1] = n
        return tuple(p.s.poz)


class Kont:
    """Atrapa środowiska runa_klik: kontenery() z listą przedmiotów (id -> ilość)."""
    def __init__(k, przedmioty): k.p = przedmioty
    def kontenery(k):
        return [{"nazwa": "backpack", "id": 2854, "przedmioty": [{"slot": i, "id": i_, "ilosc": n} for i, (i_, n) in enumerate(k.p.items())]}]


STRZALY = []      # (runa_id, cel_id)
ZROB = []         # (klawisz, koszt)
ZROB_WYNIKI = []


def _strzel(env, cel, runa_id=0, **kw):
    kont = env.kontenery()
    STRZALY.append((runa_id, cel.get("id")))
    if runa_klik._ilosc(kont, runa_id) <= 0:
        return {"wynik": "brak_runy", "powod": f"brak runy {runa_id}"}
    return {"wynik": "ok", "powod": "atrapa"}


def _zrob(env, slot=None, klawisz=None, koszt=None):
    ZROB.append((klawisz, koszt))
    return ZROB_WYNIKI.pop(0) if ZROB_WYNIKI else {"wynik": "ok", "powod": "ok", "alarm": False, "czas_s": 4.5, "rzuty": 1}


runa_klik.strzel = _strzel
uh.zrob_runa = _zrob
uh.naprawa = lambda env, *a, **k: {"wynik": "ok", "powod": "nic do naprawy", "alarm": False, "kroki": []}
ATAKI = []
ALARMY = []


def zrob(s, tryb=1, potwory=("troll",), przedmioty=None, **ust):
    """Cavebot na trasie (zwykły tryb). przedmioty = zawartość plecaka (id -> ilość) dla run; ust = nadpisania stałych cavebota."""
    for k, v in DOMYSLNE.items():
        setattr(cavebot, k, v)
    cavebot.TRYB_OBRONNY = tryb
    cavebot.ZDROWIE_CZAR_AKTYWNY = 1
    cavebot.UH_AKTYWNY = 0
    for k, v in ust.items():
        setattr(cavebot, k, v)
    ATAKI.clear(); STRZALY.clear(); ZROB.clear(); ZROB_WYNIKI.clear(); ALARMY.clear(); LOGI.clear()
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: ["mięso"], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, Z) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: ATAKI.append(m["nazwa"]), alarm=lambda w: ALARMY.append(w), spij=s.spij,
                        zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5", potwory=list(potwory))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.jz_odczyt = (0.0, 10)
    b.uh_restore = False
    b.runa_klik_env = Kont(przedmioty if przedmioty is not None else {})
    b.uh_env = types.SimpleNamespace(stan={})
    return b


def tick(s, b, n=1, dt=0.5):
    for _ in range(n):
        s.t += dt
        b.tick()


def mob(nazwa, x, y, i, hp=100, **kw):
    return dict({"id": i, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": Z, "hp": hp}, **kw)


def log_ma(txt):
    return any(txt in l for l in LOGI)


# 0. kontrakt: domyślnie wyłączone, pokrętła opisane i walidowane
sprawdz("0a TRYB_OBRONNY domyślnie 0", DOMYSLNE["TRYB_OBRONNY"] == 0)
sprawdz("0b UH_REZERWA_LECZ domyślnie 0, UH_LECZ_* puste (zero zmian)",
        DOMYSLNE["UH_REZERWA_LECZ"] == 0 and DOMYSLNE["UH_LECZ_KLAWISZ"] == "" and DOMYSLNE["UH_LECZ_KOSZT"] == 0)
nowe = ("TRYB_OBRONNY", "OBRONA_WROG_ODL", "OBRONA_PK_ODL", "OBRONA_BIJ_HP", "OBRONA_LECZ_HP", "OBRONA_OSTATECZNOSC_HP",
        "OBRONA_BLOK_S", "OBRONA_BLOK_WALKA_S", "OBRONA_ROB_RUNE_MIN_HP", "UH_REZERWA_LECZ", "UH_REZERWA_LECZ_UL", "UH_LECZ_KOSZT",
        "UH_LECZ_RUNA_ID", "OBRONA_RUNA_ID2")
sprawdz("0c pokrętła w ZAKRESY i w cavebot.py", all(k in pokretla.ZAKRESY and hasattr(cavebot, k) for k in nowe),
        [k for k in nowe if k not in pokretla.ZAKRESY or not hasattr(cavebot, k)])
sprawdz("0d pola tekstowe UH_LECZ_*", "UH_LECZ_KLAWISZ" in pokretla.TEKSTY and "UH_LECZ_CZAR" in pokretla.TEKSTY
        and pokretla.waliduj({"UH_LECZ_KLAWISZ": "F7", "UH_LECZ_CZAR": "adura vita"})[1] == []
        and pokretla.waliduj({"UH_LECZ_KLAWISZ": "F13"})[1] != [])
sprawdz("0e Karol włącza, analityk nie",
        pokretla.waliduj({"TRYB_OBRONNY": 1, "UH_REZERWA_LECZ": 100, "UH_LECZ_KOSZT": 100})[0] == {"TRYB_OBRONNY": 1, "UH_REZERWA_LECZ": 100, "UH_LECZ_KOSZT": 100}
        and pokretla.waliduj({"TRYB_OBRONNY": 1}, {"TRYB_OBRONNY": 0})[0] == {}
        and pokretla.waliduj({"UH_REZERWA_LECZ": 50}, {"UH_REZERWA_LECZ": 100})[0] == {}
        and pokretla.waliduj({"TRYB_OBRONNY": 2})[0] == {})
pk = pokretla.Pokretla(cavebot, plik=TMP / "nz.json", log=lambda t: None)
(TMP / "nz.json").write_text('{"TRYB_OBRONNY": 1, "UH_LECZ_KLAWISZ": "F7", "UH_LECZ_KOSZT": 100}'); pk.odswiez()
sprawdz("0f na_zywo.json (per instancja) włącza i wyłącza bez restartu pliku",
        cavebot.TRYB_OBRONNY == 1 and cavebot.UH_LECZ_KLAWISZ == "F7" and cavebot.UH_LECZ_KOSZT == 100)
(TMP / "nz.json").write_text("{}"); pk.mtime = None; pk.odswiez()
sprawdz("0g powrót do domyślnych", cavebot.TRYB_OBRONNY == 0 and cavebot.UH_LECZ_KLAWISZ == "" and cavebot.UH_LECZ_KOSZT == 0)

# 1. incydent (a): Orc Warrior spoza --potwory bije nas, cel Troll z odl 4: tryb obronny bije Orca, wyłączony nie
for tryb in (1, 0):
    s = Swiat(hp=76.0, mana=100); s.stwory = [mob("Orc Warrior", 100, 101, 20), mob("Troll", 104, 100, 10)]
    b = zrob(s, tryb)
    tick(s, b, 12)
    if tryb:
        sprawdz("1a TRYB_OBRONNY=1: Orc Warrior spoza --potwory bity", "Orc Warrior" in ATAKI, ATAKI)
        sprawdz("1b log [OBRONA] ... bijemy go", log_ma("[OBRONA] Orc Warrior") and log_ma("poza listą --potwory"), LOGI[-5:])
    else:
        sprawdz("1c TRYB_OBRONNY=0: Orc Warrior NIE jest bity (stare zachowanie)", "Orc Warrior" not in ATAKI, ATAKI)

# 2. Orc spoza listy stoi obok, HP wysokie i nic nie bije: nie ruszamy go (tylko gdy bije albo HP <= OBRONA_BIJ_HP)
s = Swiat(hp=100.0, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20), mob("Troll", 104, 100, 10)]
b = zrob(s, 1); tick(s, b, 6)
sprawdz("2 pełne HP, Orc nie bije: poza listą nie jest celem", "Orc Warrior" not in ATAKI, ATAKI)

# 3. HP poniżej progu ucieczki, wróg w zwarciu: walczymy zamiast uciekać; wyłączony = stara ucieczka
for tryb in (1, 0):
    s = Swiat(hp=25.0, mana=100, dmg=0.0); s.stwory = [mob("Troll", 101, 100, 10)]
    b = zrob(s, tryb); tick(s, b, 2)
    if tryb:
        sprawdz("3a TRYB_OBRONNY=1: HP 25% (< próg 30%) i troll obok: BEZ ucieczki", not b.ucieczka and b.obrona_wl, (b.ucieczka, b.obrona_wl))
        sprawdz("3b log 'walczę i leczę się zamiast uciekać'", log_ma("walczę i leczę się zamiast uciekać"), LOGI[-4:])
    else:
        sprawdz("3c TRYB_OBRONNY=0: ta sama sytuacja = ucieczka (stare)", b.ucieczka, b.ucieczka)

# 4. leczenie: (1) runa leczenia z plecaka na siebie
s = Swiat(hp=25.0, mana=150, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={UH_ID: 2, BLANK: 3}, UH_LECZ_KLAWISZ="F7", UH_LECZ_KOSZT=100, UH_LECZ_CZAR="adura vita")
tick(s, b, 3)
sprawdz("4a runa leczenia (3160) z plecaka użyta na siebie", any(r == UH_ID and c is None for r, c in STRZALY), STRZALY)
sprawdz("4b nie robimy runy, gdy jest w plecaku", not ZROB, ZROB)
sprawdz("4c brak ucieczki", not b.ucieczka, b.ucieczka)

# 5. (2) brak runy w plecaku + blank + mana >= koszt: ROBIMY ją w walce (czar leczący z UH_LECZ_*, nie UH_CZAR=HMM)
s = Swiat(hp=25.0, mana=150, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={BLANK: 3, HMM_ID: 5}, UH_LECZ_KLAWISZ="F7", UH_LECZ_KOSZT=100, UH_LECZ_CZAR="adura vita")
wyl0 = b.uh_wylaczony_do
tick(s, b, 3)
sprawdz("5a robi runę leczenia w walce (F7, koszt 100)", ZROB and ZROB[0] == ("F7", 100), ZROB)
sprawdz("5b UH_CZAR/klawisz/koszt uh.py przywrócone po robieniu", uh.UH_KLAWISZ == cavebot.UH_KLAWISZ and uh.UH_KOSZT == cavebot.UH_KOSZT
        and uh.UH_CZAR == cavebot.UH_CZAR, (uh.UH_KLAWISZ, uh.UH_KOSZT, uh.UH_CZAR))
sprawdz("5c log o robieniu w walce", log_ma("robię ją W WALCE") and log_ma("robienie runy leczenia: ok"), LOGI[-6:])
sprawdz("5d UH nie wyłączony", b.uh_wylaczony_do == wyl0, b.uh_wylaczony_do)

# 5e. samo UH_CZAR="adori gran" (HMM), bez UH_LECZ_*: runy leczenia NIE robimy (HMM nie leczy), exura zamiast
s = Swiat(hp=25.0, mana=150, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={BLANK: 3})
tick(s, b, 3)
sprawdz("5e bez czaru leczącego (UH_CZAR=adori gran) runy leczenia nie robimy", not ZROB and tryb_obronny.lecz_czar(b) is None, ZROB)
sprawdz("5f ... a exura (F2) leczy", "F2" in s.klawisze and not b.ucieczka, (s.klawisze, b.ucieczka))
b2 = zrob(Swiat(), 1, UH_CZAR="adura vita", UH_KLAWISZ="F7", UH_KOSZT=100)
sprawdz("5g UH_CZAR leczący (adura vita) wystarcza bez UH_LECZ_*", tryb_obronny.lecz_czar(b2) == ("adura vita", "F7", 100), tryb_obronny.lecz_czar(b2))

# 6. brak blanka: nie próbujemy, NIE wyłączamy UH na 10 min, przechodzimy do exury
s = Swiat(hp=25.0, mana=150, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={}, UH_LECZ_KLAWISZ="F7", UH_LECZ_KOSZT=100, UH_LECZ_CZAR="adura vita")
wyl0 = b.uh_wylaczony_do
tick(s, b, 3)
sprawdz("6a brak blanka: zrob_runa nie wołane", not ZROB, ZROB)
sprawdz("6b exura leczy zamiast", "F2" in s.klawisze, s.klawisze)
sprawdz("6c UH_PRZERWA_BRAK_BLANK_S nie zastosowane", b.uh_wylaczony_do == wyl0, b.uh_wylaczony_do)
# 6d. blank jest w odczycie, ale uh zgłasza brak_blank: też bez 10-minutowej przerwy
s = Swiat(hp=25.0, mana=150, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={BLANK: 1}, UH_LECZ_KLAWISZ="F7", UH_LECZ_KOSZT=100, UH_LECZ_CZAR="adura vita")
ZROB_WYNIKI.append({"wynik": "brak_blank", "powod": "brak blank run", "alarm": False, "czas_s": 1.0})
wyl0 = b.uh_wylaczony_do
tick(s, b, 4)
sprawdz("6d brak_blank z uh.py: UH nie wyłączony na 10 min, kolejna próba odroczona",
        b.uh_wylaczony_do == wyl0 and b.obrona_blank_do > s.t and len(ZROB) == 1, (b.uh_wylaczony_do, b.obrona_blank_do, ZROB))

# 7. ostateczność: HP < 20% i brak many/run/blanka = ucieczka; HP >= 20% walczymy dalej
s = Swiat(hp=15.0, mana=10, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={}); tick(s, b, 2)
sprawdz("7a HP 15%, mana 10, brak run i blanka: ucieczka (ostateczność)", b.ucieczka and log_ma("ostateczność"), (b.ucieczka, LOGI[-3:]))
s = Swiat(hp=22.0, mana=10, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={}); tick(s, b, 2)
sprawdz("7b HP 22% (>= 20%), te same braki: jeszcze walczymy, bez ucieczki", not b.ucieczka and b.obrona_wl, (b.ucieczka, b.obrona_wl))
s = Swiat(hp=15.0, mana=60, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={}); tick(s, b, 2)
sprawdz("7c HP 15% ale mana na exurę: nie uciekamy, leczymy", not b.ucieczka and "F2" in s.klawisze, (b.ucieczka, s.klawisze))
s = Swiat(hp=15.0, mana=10, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={UH_ID: 1}); tick(s, b, 2)
sprawdz("7d HP 15%, runa leczenia w plecaku: nie uciekamy, runa na siebie", not b.ucieczka and any(r == UH_ID for r, _ in STRZALY), (b.ucieczka, STRZALY))
s = Swiat(hp=12.0, mana=150, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={BLANK: 2}, ZDROWIE_CZAR_AKTYWNY=0, UH_LECZ_KLAWISZ="F7", UH_LECZ_KOSZT=100, UH_LECZ_CZAR="adura vita")
tick(s, b, 2)
sprawdz("7e HP 12% (< OBRONA_ROB_RUNE_MIN_HP) bez exury: runy w walce nie robimy (4-5 s), ucieczka", b.ucieczka and not ZROB, (b.ucieczka, ZROB))

# 8. blokada kroków ucieczki: mob na polu kroku, pozycja stoi -> bijemy blokującego
for tryb in (1, 0):
    s = Swiat(hp=22.0, mana=10, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
    b = zrob(s, tryb, przedmioty={})
    b.ucieczka = True; b.ucieczka_od = 0.0; b.ruch_czas = 0.0; b.idx = 3
    tick(s, b, 12)
    if tryb:
        sprawdz("8a TRYB_OBRONNY=1: ucieczka stoi przez moba -> Orc Warrior bity", "Orc Warrior" in ATAKI, ATAKI)
        sprawdz("8b log 'bijemy blokującego'", log_ma("bijemy blokującego"), LOGI[-4:])
    else:
        sprawdz("8c TRYB_OBRONNY=0: kręci się w kółko, nie atakuje (stare)", "Orc Warrior" not in ATAKI, ATAKI)
s = Swiat(hp=22.0, mana=10, dmg=0.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={}); b.ucieczka = True; b.ucieczka_od = 0.0; b.idx = 3
tick(s, b, 1); b.ruch_czas = s.t        # dopiero co ruszyliśmy: to jeszcze nie blokada
tick(s, b, 1, dt=0.3)
sprawdz("8d ruch w ostatniej chwili: bez bicia blokującego", "Orc Warrior" not in ATAKI, ATAKI)

# 9. gracze: tylko z czaszką
skull = {"id": 50, "nazwa": "Zbir", "gracz": True, "x": 101, "y": 100, "z": Z, "hp": 100, "czaszka": True}
miły = {"id": 51, "nazwa": "Milek", "gracz": True, "x": 101, "y": 100, "z": Z, "hp": 100}
s = Swiat(hp=70.0, dmg=3.0); s.stwory = [dict(skull)]
b = zrob(s, 1); tick(s, b, 8)
sprawdz("9a gracz Z CZASZKĄ obok, bije nas: bity", "Zbir" in ATAKI, ATAKI)
sprawdz("9b ... i nie startuje ucieczka PK do depo", b.pk_stan is None, b.pk_stan)
s = Swiat(hp=70.0, dmg=3.0); s.stwory = [dict(miły)]
b = zrob(s, 1); tick(s, b, 8)
sprawdz("9c gracz BEZ czaszki nie jest bity", "Milek" not in ATAKI, ATAKI)
s = Swiat(hp=70.0, dmg=3.0); s.stwory = [dict(skull)]
b = zrob(s, 0); tick(s, b, 8)
sprawdz("9d TRYB_OBRONNY=0: gracz z czaszką nie jest bity (stare)", "Zbir" not in ATAKI, ATAKI)
s = Swiat(hp=70.0, dmg=3.0); s.stwory = [dict(skull)]
b = zrob(s, 1, OBRONA_PK_ODL=0); tick(s, b, 8)
sprawdz("9e OBRONA_PK_ODL=0: graczy nie bijemy", "Zbir" not in ATAKI, ATAKI)
s = Swiat(hp=70.0, dmg=3.0); skull4 = dict(skull, x=104); s.stwory = [skull4]
b = zrob(s, 1); tick(s, b, 4)
sprawdz("9f gracz z czaszką daleko (4 pola): nie bijemy go", "Zbir" not in ATAKI, ATAKI)
s = Swiat(hp=15.0, mana=10, dmg=0.0); s.stwory = [dict(skull)]
b = zrob(s, 1, przedmioty={}); tick(s, b, 3)
sprawdz("9g gracz z czaszką, HP 15% bez środków: ostateczność (PK do depo / ucieczka, nie walka)",
        b.pk_stan is not None or b.ucieczka, (b.pk_stan, b.ucieczka))

# 10. runy ataku w obronie nawet przy RUNA_AKTYWNA=0
s = Swiat(hp=70.0, mana=100, dmg=3.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={HMM_ID: 5, BLANK: 1}, RUNA_AKTYWNA=0, RUNA_TRYB_KLIK=0, ZDROWIE_CZAR_AKTYWNY=0)
tick(s, b, 10)
sprawdz("10a RUNA_AKTYWNA=0: w obronie strzał HMM (3198) w Orca", any(r == HMM_ID and c == 20 for r, c in STRZALY), STRZALY)
s = Swiat(hp=70.0, mana=100, dmg=3.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 0, przedmioty={HMM_ID: 5}, RUNA_AKTYWNA=0, ZDROWIE_CZAR_AKTYWNY=0)
tick(s, b, 10)
sprawdz("10b TRYB_OBRONNY=0: runy ataku nadal tylko przy RUNA_AKTYWNA=1", not STRZALY, STRZALY)
s = Swiat(hp=70.0, mana=100, dmg=3.0); s.stwory = [mob("Orc Warrior", 100, 101, 20)]
b = zrob(s, 1, przedmioty={3155: 5}, RUNA_AKTYWNA=0, OBRONA_RUNA_ID2=3155, ZDROWIE_CZAR_AKTYWNY=0)
tick(s, b, 10)
sprawdz("10c brak HMM, druga runa ataku (SD 3155) z OBRONA_RUNA_ID2", any(r == 3155 for r, _ in STRZALY), STRZALY)

# 11. rezerwa many na leczenie przy robieniu run w spokoju
def uh_spokoj(mana, max_mana, rez, koszt=70, mana_min=70):
    s = Swiat(hp=100.0, mana=mana, max_mana=max_mana)
    b = zrob(s, 0, UH_AKTYWNY=1, UH_KOSZT=koszt, UH_MANA_MIN=mana_min, UH_REZERWA_LECZ=rez)
    b.uh_naprawa_ok = True
    tick(s, b, 4)
    return len(ZROB)


sprawdz("11a rezerwa 0 (dziś): mana 120/185 >= 70 -> runa", uh_spokoj(120, 185, 0) == 1)
sprawdz("11b rezerwa 100: mana 120/185 < 70+100 -> czeka", uh_spokoj(120, 185, 100) == 0)
sprawdz("11c rezerwa 100: mana 170/185 = 70+100 -> runa", uh_spokoj(170, 185, 100) == 1)
sprawdz("11d mała mana: max 100, rezerwa = min(100, 55) = 55, wymagane 125 ograniczone do max 100: 99 czeka, 100 robi",
        uh_spokoj(99, 100, 100) == 0 and uh_spokoj(100, 100, 100) == 1)
sprawdz("11e UH_MANA_MIN wyższe niż koszt+rezerwa nadal obowiązuje", uh_spokoj(150, 185, 20, mana_min=160) == 0)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
