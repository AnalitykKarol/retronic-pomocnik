"""Obrona przed graczami (obrona_pk.py + haki w cavebot.py/wyprawa.py), wymaganie 1 SPEC_obrona_pk_1015.
Odtwarza sekwencję z logu mozg-20261015-1807 (20:34:56 - 20:35:13: Krzyssxd i Brezniev Leonid, HP 100 -> 82 -> 48%)
na atrapach: detekcja ma wystrzelić o 20:35:06 i nie wcześniej; potwór przy nas = nie PK; lista wrogów trwała;
wróg znów w widoku = natychmiastowa ucieczka; karencja blokuje powrót. Plus plan trasy do depo Edron na prawdziwych
plikach tras i mapie. Nic nie trafia do gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot
import cavebot
import obrona_pk
import wyprawa as W

cavelog = []
_log0 = cavebot.log


def _log(*a):
    cavelog.append(" ".join(map(str, a)))
    _log0(*a)


cavebot.log = _log
cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.ODWROCENIE_TRASY = 0.0
cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.ZDROWIE_CZAR_AKTYWNY = 0       # exura w ticku zwykłym wyłączona: test PK sprawdza własne leczenie PK
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


JA = (100, 100, 8)


def gr(nick, dx, dy, z=8, gracz=True, hp=100, id_=None):
    return {"id": id_ or (hash(nick) % 100000 + 10), "nazwa": nick, "gracz": gracz, "dx": dx, "dy": dy,
            "z": z, "hp": hp}


def troll(i, dx, dy):
    return gr("Troll", dx, dy, gracz=False, id_=500 + i)


class Swiat:
    """Klatki {t: (hp, [stwory])}: zapytanie bierze ostatnią klatkę z t <= s.t. Czas ustawia test (s.t = t)."""

    def __init__(s, klatki, mana=0, max_mana=0):
        s.t = 0.0
        s.klatki = sorted(klatki, key=lambda k: k[0])
        s.poz = list(JA)
        s.klawisze, s.alarmy, s.ataki = [], [], []
        s.mana, s.max_mana = mana, max_mana

    def klatka(s):
        k = s.klatki[0]
        for x in s.klatki:
            if x[0] <= s.t:
                k = x
        return k

    def zegar(s):
        return s.t

    def spij(s, d):
        pass                              # czas klatek ustawia test, nie ticki

    def zapytaj(s, z):
        _, hp, st = s.klatka()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": hp, "max_hp": 100, "mana": s.mana, "max_mana": s.max_mana}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            # klatki opisują stwory względem postaci (bot idzie trasą, więc pozycje bezwzględne liczymy tu)
            out = []
            for m in st:
                m = dict(m)
                m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        d = bot.KIERUNEKI[k] if hasattr(bot, "KIERUNEKI") else bot.KIERUNKI[k]
        p.s.poz[0] += d[0]
        p.s.poz[1] += d[1]
        return tuple(p.s.poz)


class FakeWyprawa:
    """Atrapa Wyprawa: zapamiętuje wywołania start_pk; `ok=False` = brak planu trasy."""

    def __init__(f, cb_ref):
        f.cb = cb_ref
        f.w = None
        f.ok = True
        f.zablokowany = False
        f.wywolania = []
        f.depo = JA                   # pole depo (domyślnie tu, gdzie stoi postać: start w karencji = czekanie)

    def _pole_depo(f):
        return f.depo

    def start_pk(f, rodzaj, teraz, baza=None):
        f.wywolania.append((rodzaj, teraz))
        if not f.ok:
            return False
        f.w = {"potrzeby": {"depo": True, "pk": rodzaj}}
        f.cb[0].wypad_aktywny = True
        return True

    def tick(f):
        return False

    def przerwij(f, powod):
        f.w = None
        f.cb[0].wypad_aktywny = False

    def uciekaj(f, poz):
        return True


def zrob(s, wyprawa=True, wrogowie=None, **kw):
    def atak(m, g):
        s.ataki.append((m["id"], s.t))

    lootlog = []
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    punkty = [(100 + i, 100, 8) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak,
                        alarm=lambda w: s.alarmy.append(w), spij=s.spij, zegar=s.zegar, loot=loot, **kw)
    b.pk_det, b.pk_wrogowie = None, None
    det_dummy, wr = b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(wrogowie or (TMP / f"wrogowie-{len(ok)}.json"), czas=s.zegar,
                                       log=lambda t: None)
    b.powiadomienia = []
    b._pk_powiadom = lambda tytul, tresc, klucz: b.powiadomienia.append((tytul, tresc, klucz))
    ref = [b]
    b.fw = None
    if wyprawa:
        b.fw = FakeWyprawa(ref)
        b.wyprawa = b.fw
    return b


def odtworz(b, s, od, do, krok=1.0, fn=None):
    """Ticki co `krok` s od t=od do t=do (włącznie). -> (pierwsze t ze stanem PK albo None)."""
    pierwsze = None
    t = od
    while t <= do + 1e-9:
        s.t = t
        if fn:
            fn(t)
        b.tick()
        if pierwsze is None and b.pk_stan is not None:
            pierwsze = t
        t += krok
    return pierwsze


# --- sekwencja z logu: t=0 -> 20:34:56, t=10 -> 20:35:06, t=17 -> 20:35:13 ---
def klatki_realne():
    tr = [troll(1, -3, 1), troll(2, 4, 3), troll(3, -5, -2)]
    k = []
    for t in range(0, 10):          # 20:34:56 - 20:35:05: gracze się zbliżają, HP 100%, potwory daleko (>= 2 pola)
        d = max(6 - t // 2, 2)
        k.append((t, 100, [gr("Krzyssxd", 5, 2), gr("Brezniev Leonid", d, 0), gr("Ja", 0, 0, id_=9)] + tr))
    # 20:35:06: Brezniev obok (1,0), najbliższy troll 3 pola, HP 100 -> 82
    k.append((10, 82, [gr("Krzyssxd", 4, 2), gr("Brezniev Leonid", 1, 0), troll(1, -3, 1)] + tr[1:]))
    k.append((11, 74, [gr("Krzyssxd", 3, 1), gr("Brezniev Leonid", 1, 0), troll(1, -3, 1)] + tr[1:]))
    for t in range(12, 17):
        k.append((t, 66 - 2 * (t - 12), [gr("Krzyssxd", 2, 0), gr("Brezniev Leonid", 1, 0), troll(1, -3, 1)] + tr[1:]))
    # 20:35:13: Krzyssxd obok (1,0), trolle 2-5 pól, HP 48
    k.append((17, 48, [gr("Krzyssxd", 1, 0), gr("Brezniev Leonid", 1, 1), troll(1, -2, 0), troll(2, 4, 3),
                       troll(3, -5, -2)]))
    return k


# 1. replay: detekcja o 20:35:06 (t=10), nie wcześniej; atak PK z danych, bez modelu
s = Swiat(klatki_realne())
b = zrob(s)
pierwsze = odtworz(b, s, 0, 17)
sprawdz("1 replay 20:34:56-20:35:13: ucieczka PK startuje dokładnie o 20:35:06 (t=10)", pierwsze == 10, f"pierwsze={pierwsze}")
sprawdz("1a przed 20:35:06 gracze blisko (2 pola) przy pełnym HP nie wywołują PK", pierwsze is None or pierwsze >= 10)
sprawdz("1b start_pk('ucieczka') wywołany raz, plan z danych (bez fallbacku)",
        b.fw.wywolania[:1] == [("ucieczka", 10.0)] and not b.pk_fallback and b.pk_stan == "UCIECZKA",
        f"{b.fw.wywolania} fallback={b.pk_fallback} stan={b.pk_stan}")
sprawdz("1c ucieczka z progu HP nie cofa nas w głąb (HP 48%): ucieczka=False przy marszu do depo", b.ucieczka is False)
sprawdz("1d alarm + powiadomienie (critical) o ataku", len(s.alarmy) >= 1 and any(k == "pk_atak" for _, _, k in b.powiadomienia),
        f"alarmy={s.alarmy} pow={b.powiadomienia}")
d = json.loads(Path(b.pk_wrogowie.plik).read_text())
nicki = {v["nick"] for v in d["wrogowie"].values()}
sprawdz("1e lista wrogów w pliku: Brezniev Leonid (atak o t=10)", "Brezniev Leonid" in nicki, f"{nicki}")
sprawdz("1f drugi napastnik (Krzyssxd obok, HP 74 -> 48) też na liście wrogów", "Krzyssxd" in nicki, f"{nicki}")
sprawdz("1g plik wrogów: zapis atomowy (bez .tmp), karencja_do w przyszłości",
        not Path(str(b.pk_wrogowie.plik) + ".tmp").exists() and d["karencja_do"] > 17 + 29 * 60, f"{d.get('karencja_do')}")
sprawdz("1h wpis wroga ma czas, liczbę ataków i miejsce",
        all({"od", "ost", "ile", "powod", "miejsce"} <= set(v) for v in d["wrogowie"].values()), f"{d}")
sprawdz("1i bez pytania modelu: wystarczyły dane (log 'ATAK gracza z danych')",
        any("ATAK gracza z danych" in l and "Brezniev" in l for l in cavelog))

# 2. potwór obok + spadek HP + gracz blisko = NIE PK (to bije potwór)
s = Swiat([(0, 100, [gr("Brezniev Leonid", 2, 0), troll(1, 1, 0)]), (1, 80, [gr("Brezniev Leonid", 1, 0), troll(1, 1, 0)]),
           (2, 70, [gr("Brezniev Leonid", 1, 0), troll(1, 1, 0)])])
b = zrob(s)
pierwsze = odtworz(b, s, 0, 3)
sprawdz("2 troll obok + spadek HP + gracz obok: to nie PK", pierwsze is None and not b.pk_wrogowie.dane and not b.fw.wywolania,
        f"pierwsze={pierwsze} wr={b.pk_wrogowie.dane}")

# 3. własne widmo (ten sam nick po relogu) obok + spadek HP = NIE PK; GM obok = NIE PK
s = Swiat([(0, 100, [gr("Ja", 3, 0, id_=77)]), (1, 70, [gr("Ja", 1, 0, id_=77)]), (2, 60, [gr("ja ", 1, 0, id_=77)])])
b = zrob(s)
pierwsze = odtworz(b, s, 0, 3)
sprawdz("3 widmo własnej postaci obok przy spadku HP: nie PK", pierwsze is None, f"{pierwsze}")
s = Swiat([(0, 100, [gr("GM Sailes", 3, 0)]), (1, 70, [gr("GM Sailes", 1, 0)]), (2, 60, [gr("GM Sailes", 1, 0)])])
b = zrob(s)
pierwsze = odtworz(b, s, 0, 3)
sprawdz("3b GM obok przy spadku HP: nie PK (GM obsługuje stan GRACZ)", pierwsze is None, f"{pierwsze}")

# 4. mały spadek (poniżej PK_SPADEK_PP) i gracz poza PK_ODL: bez reakcji
s = Swiat([(0, 100, [gr("Brezniev Leonid", 1, 0)]), (1, 96, [gr("Brezniev Leonid", 1, 0)]),
           (2, 80, [gr("Brezniev Leonid", 3, 0)]), (3, 60, [gr("Brezniev Leonid", 3, 0)])])
b = zrob(s)
pierwsze = odtworz(b, s, 0, 3)
sprawdz("4 spadek 4 pp (obok) i spadek 20 pp (gracz 3 pola, PK_ODL=1): bez PK", pierwsze is None, f"{pierwsze}")
s = Swiat([(0, 100, [gr("Brezniev Leonid", 3, 0)]), (1, 80, [gr("Brezniev Leonid", 3, 0)])])
cavebot.PK_ODL_CZAR = 4
b = zrob(s)
pierwsze = odtworz(b, s, 0, 2)
cavebot.PK_ODL_CZAR = 0
sprawdz("4b PK_ODL_CZAR=4: gracz 3 pola + spadek 20 pp = atak z zasięgu czaru", pierwsze == 1, f"{pierwsze}")

# 5. pokrętło PK_OBRONA=0 wyłącza
s = Swiat(klatki_realne())
cavebot.PK_OBRONA = 0
b = zrob(s)
pierwsze = odtworz(b, s, 0, 17)
cavebot.PK_OBRONA = 1
sprawdz("5 PK_OBRONA=0: ta sama sekwencja nie uruchamia ucieczki PK", pierwsze is None and not b.pk_wrogowie.dane, f"{pierwsze}")

# 6. wróg z listy znów w widoku (nowa sesja, plik wrogów trwały): ucieczka od razu, zanim uderzy
plik = TMP / "wrogowie-trwaly.json"
s = Swiat(klatki_realne())
b = zrob(s, wrogowie=plik)
odtworz(b, s, 0, 17)
b = None
s2 = Swiat([(0, 100, [gr("Krzyssxd", 5, 3)]), (1, 100, [gr("Krzyssxd", 4, 3)])])
b2 = zrob(s2, wrogowie=plik)
pierwsze = odtworz(b2, s2, 0, 1, krok=0.5)
sprawdz("6 znany wróg w widoku, HP 100%: natychmiastowa ucieczka PK (przed ciosem)", pierwsze == 0 and b2.fw.wywolania[:1] == [("ucieczka", 0.0)],
        f"pierwsze={pierwsze} {b2.fw.wywolania}")
s3 = Swiat([(0, 100, [gr("Nieznany Gracz", 5, 3)]), (1, 100, [gr("Nieznany Gracz", 1, 0)])])
b3 = zrob(s3, wrogowie=plik)
odtworz(b3, s3, 0, 1)
sprawdz("6b nieznany gracz w widoku bez ataku: bez ucieczki (jest tylko czekanie po starcie w karencji)",
        not b3.fw.wywolania and b3.pk_stan in (None, "DEPO"), f"{b3.fw.wywolania} {b3.pk_stan}")
s4 = Swiat([(0, 100, [gr("krzyssxd", 5, 3)])])        # inna wielkość liter = ten sam nick
b4 = zrob(s4, wrogowie=plik)
sprawdz("6c nick wroga porównywany bez wielkości liter", odtworz(b4, s4, 0, 0) == 0)

# 7. wróg zbyt dawno widziany (PK_WROG_WAZNY_H) nie wywołuje ucieczki na sam widok
plik7 = TMP / "wrogowie-stary.json"
plik7.write_text(json.dumps({"wrogowie": {"stary wrog": {"nick": "Stary Wrog", "od": 0, "ost": 0, "ile": 1}}, "karencja_do": 0}))
s = Swiat([(0, 100, [gr("Stary Wrog", 5, 3)])])
b = zrob(s, wrogowie=plik7)
s.t = 4 * 24 * 3600.0
b.tick()
sprawdz("7 wróg sprzed 4 dni (PK_WROG_WAZNY_H=72) nie wywołuje ucieczki", b.pk_stan is None and not b.fw.wywolania)

# 8. karencja blokuje powrót: dotarcie do depo -> czekanie, powrót dopiero po karencji i bez wroga w widoku
s = Swiat([(0, 100, [gr("Krzyssxd", 6, 0)]), (50, 100, []), (4000, 100, []), (4100, 100, [gr("Krzyssxd", 6, 0)]),
           (4300, 100, [])])
b = zrob(s, wrogowie=TMP / "wrogowie-karencja.json")
b.pk_wrogowie.dodaj("Krzyssxd", "atak", JA)
s.t = 0.0
b.tick()                                        # znany wróg w widoku: ucieczka
b.fw.w = None
b.wypad_aktywny = False
b._pk_wyprawa_koniec("ucieczka", "depo", "jestem w depo", (110, 100, 8))   # wyprawa melduje dotarcie
sprawdz("8a dotarcie do depo: stan DEPO, powiadomienie o depo", b.pk_stan == "DEPO" and any(k == "pk_depo" for _, _, k in b.powiadomienia))
karencja_s = cavebot.PK_KARENCJA_MIN * 60.0
for t in (50, 60, 600, 1700):
    s.t = float(t)
    b.tick()
sprawdz("8b w karencji (30 min od ostatniego widoku) wyprawa powrotna NIE startuje",
        b.pk_stan == "DEPO" and [w for w in b.fw.wywolania if w[0] == "powrot"] == [], f"{b.fw.wywolania}")
s.t = 4000.0                                    # po karencji (ostatni widok t=0, karencja do 1800 s), wróg poza widokiem
b.tick()
sprawdz("8c po karencji i bez wroga: start powrotu na spot", [w[0] for w in b.fw.wywolania if w[0] == "powrot"] == ["powrot"]
        and b.pk_stan == "POWROT", f"{b.fw.wywolania} stan={b.pk_stan}")
s.t = 4100.0
b.tick()                                        # wróg znów w widoku w drodze powrotnej
sprawdz("8d wróg w widoku w drodze powrotnej: znów ucieczka do depo", b.fw.wywolania[-1][0] == "ucieczka" and b.pk_stan == "UCIECZKA",
        f"{b.fw.wywolania} stan={b.pk_stan}")
b._pk_wyprawa_koniec("ucieczka", "depo", "depo", (110, 100, 8))
s.t = 4100.0 + 100
b.tick()
sprawdz("8e w depo z wrogiem w widoku po karencji: nie wracamy (czekamy)", b.pk_stan == "DEPO")
b.pk_wrogowie.karencja_do = 0.0
s.t = 4350.0
b.tick()
sprawdz("8f dopiero gdy karencja minęła i wróg zniknął: powrót", b.pk_stan == "POWROT", f"{b.pk_stan}")
b.fw.w, b.wypad_aktywny = None, False                  # Wyprawa._zakoncz_pk sprząta przed zdarzeniem końca
b._pk_wyprawa_koniec("powrot", "depo", "na spocie", (101, 100, 8))
sprawdz("8g powrót zakończony: koniec obrony, bot wraca do normalnej gry", b.pk_stan is None and b.wypad_aktywny is False)

# 9. ucieczka awaryjna (brak planu): stary stan UCIECZKA, bez powrotu przy zdrowiu < karencji; ponowienie trasy
s = Swiat([(0, 100, []), (10, 100, [gr("Brezniev Leonid", 2, 0)]), (11, 80, [gr("Brezniev Leonid", 1, 0)]),
           (12, 100, []), (200, 100, []), (4000, 100, [])])
b = zrob(s)
b.fw.ok = False
odtworz(b, s, 0, 12)
sprawdz("9 brak planu trasy: ucieczka awaryjna (stan UCIECZKA, fallback)", b.pk_stan == "UCIECZKA" and b.pk_fallback and b.ucieczka,
        f"stan={b.pk_stan} fb={b.pk_fallback} uc={b.ucieczka}")
for t in (30, 90, 200, 600):
    s.t = float(t)
    b.tick()
sprawdz("9a HP wróciło do 100%, wróg poza widokiem, ale karencja trwa: nadal ucieczka (nie wracamy na spot)",
        b.ucieczka and b.pk_stan == "UCIECZKA", f"uc={b.ucieczka} stan={b.pk_stan}")
n_prob = len(b.fw.wywolania)
sprawdz("9b w ucieczce awaryjnej ponawiamy budowę trasy do depo (co PK_FALLBACK_PONOW_S)", n_prob >= 3, f"{b.fw.wywolania}")
b.fw.ok = True
s.t = 700.0
b.tick()
sprawdz("9c plan stał się możliwy: przejście na marsz do depo", not b.pk_fallback and not b.ucieczka and b.fw.w is not None,
        f"fb={b.pk_fallback} uc={b.ucieczka}")
# awaryjna kończy się dopiero po karencji
s = Swiat([(0, 100, []), (10, 100, [gr("Brezniev Leonid", 2, 0)]), (11, 80, [gr("Brezniev Leonid", 1, 0)]),
           (12, 100, []), (4000, 100, [])])
b = zrob(s)
b.fw.ok = False
odtworz(b, s, 0, 12)
s.t = 4000.0
for _ in range(3):
    b.tick()
sprawdz("9d po karencji i pełnym HP ucieczka awaryjna się kończy", b.pk_stan is None and not b.ucieczka, f"stan={b.pk_stan} uc={b.ucieczka}")

# 10. leczenie w marszu: exura (F2) bez postoju, UH na siebie przy niskim HP
s = Swiat([(0, 100, []), (10, 100, [gr("Brezniev Leonid", 2, 0)]), (11, 70, [gr("Brezniev Leonid", 1, 0)]),
           (13, 70, [gr("Brezniev Leonid", 1, 0)]), (14, 30, [gr("Brezniev Leonid", 1, 0)]),
           (20, 30, [gr("Brezniev Leonid", 1, 0)])], mana=80, max_mana=95)
b = zrob(s)
odtworz(b, s, 0, 12)
sprawdz("10 exura (F2) w marszu do depo (HP 70%, mana 80)", "F2" in s.klawisze, f"{s.klawisze}")
import runa_klik
wywolania_uh = []
_strzel0 = runa_klik.strzel
runa_klik.strzel = lambda env, cel, **kw: (wywolania_uh.append((cel, kw)) or {"wynik": "ok", "powod": "ubyło runy"})
odtworz(b, s, 12, 14)
runa_klik.strzel = _strzel0
sprawdz("10a HP 30% w marszu: UH z plecaka na siebie (runa 3160, cel = my dx=dy=0)",
        wywolania_uh and wywolania_uh[0][0]["dx"] == 0 and wywolania_uh[0][0]["dy"] == 0 and wywolania_uh[0][1]["runa_id"] == 3160,
        f"{wywolania_uh}")
sprawdz("10b zwykłe jedzenie/GRACZ nie blokują ucieczki (stan nie GRACZ)", str(b.stan) != "GRACZ", f"{b.stan}")

# 11. GRACZ (pauza przy groźnym graczu z czaszką) nie zatrzymuje ucieczki PK
s = Swiat([(0, 100, []), (10, 100, [gr("Brezniev Leonid", 2, 0)]), (11, 70, [dict(gr("Brezniev Leonid", 1, 0), czaszka=1)]),
           (12, 70, [dict(gr("Brezniev Leonid", 1, 0), czaszka=1)])])
b = zrob(s)
odtworz(b, s, 0, 12)
sprawdz("11 gracz z czaszką w widoku podczas ucieczki PK: stan nie GRACZ (pauza by zabiła)", str(b.stan) != "GRACZ" and b.pk_stan == "UCIECZKA",
        f"{b.stan} {b.pk_stan}")

# --- wyprawa.py: plan trasy do depo Edron i powrotu na prawdziwych plikach tras ---
import mapa as _mapa
if _mapa.PLIK_MAPY.is_file():
    MAPA = _mapa.Mapa()
    baza_pk = W.punkty_bazy(nazwy=W.BAZY_PK)
    sprawdz("12 plan 'edron' jest w bazach PK, ale nie w zwykłych (wyprawa po zapasy)",
            "edron" in baza_pk and "edron" not in W.punkty_bazy() and "edron" not in W.BAZY)
    START_E = (33117, 31775, 8)

    class KonfW:
        WYPRAWA_AKTYWNA = 1
        WYPRAWA_MAX_CZAS_S = 1800
        WYPRAWA_MAX_KROKOW = 6000
        WYPRAWA_STOP_PRZY_UTKNIECIU = 1
        WYPRAWA_CO_MIN = 20
        WYPRAWA_PO_DEPO_S = 900
        WYPRAWA_DEPO_POWROT = 0
        WYPRAWA_TYLKO_DEPO = 1
        DEPO_EDRON_OBSZAR = 0        # 24.10: stare stanowisko; obszar ma test_depo_edron_obszar

    class CBW:
        mapa = MAPA

        def __init__(c):
            c.t = 0.0
            c.wypad_aktywny = False
            c.ruch_poz = START_E
            c.poz = START_E
            c.koniec = []
            c.stan = None
            c.postac = types.SimpleNamespace(pozycja=lambda: c.poz)

        def zegar(c):
            return c.t

        def gracz(c):
            return {"proc": 60.0}

        def _wypad_reset_klik(c):
            pass

        def droga(c, *a, **k):
            return []

        def pauza(c, *a):
            pass

        def ustaw_stan(c, a, b=""):
            c.stan = a

        def _pk_wyprawa_koniec(c, rodzaj, wynik, opis, poz):
            c.koniec.append((rodzaj, wynik, tuple(poz)))

    class OpsW:
        def wiadomosci(o):
            return []

    logi = []
    cbw = CBW()
    stop_plik = TMP / "STOP-pk"
    w = W.Wyprawa(cbw, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / "wp_stan.json",
                  plik_sklepow=TMP / "wp_sklepy.json", plik_npc=TMP / "wp_npc.json", plik_stop=stop_plik,
                  czas=lambda: 5_000_000.0)
    sprawdz("12a start_pk('ucieczka') z pętli Edron buduje plan do depo (cel = koniec edron_do_depo)",
            w.start_pk("ucieczka", 0.0) and w.w is not None and w.w["baza"] == "edron"
            and tuple(w.w["stops"][0]["stoi"]) == (33173, 31796, 8) and w.w["potrzeby"] == {"depo": True, "pk": "ucieczka"}
            and cbw.wypad_aktywny, f"{logi[-3:]}")
    w._zakoncz_depo("depo", "jestem w depo")
    sprawdz("12b dotarcie PK: bez pliku STOP, bez blokady wypraw, cb dostaje zdarzenie końca",
            not stop_plik.exists() and not w.zablokowany and cbw.koniec == [("ucieczka", "depo", START_E)]
            and w.w is None and not cbw.wypad_aktywny, f"{cbw.koniec} stop={stop_plik.exists()} zabl={w.zablokowany}")
    cbw.poz = (33173, 31796, 8)
    sprawdz("12c start_pk('powrot') z depo buduje trasę na łowisko (koniec edron_depo_trolle)",
            w.start_pk("powrot", 10.0, baza="edron") and w.w["potrzeby"] == {"depo": True, "pk": "powrot"}
            and tuple(w.w["stops"][0]["stoi"]) == (33117, 31775, 8), f"{logi[-3:]} {w.w and w.w['stops']}")
    w._zakoncz_depo("blad", "utknąłem")
    sprawdz("12d awaria trasy PK: też bez STOP (decyzja po stronie cavebota), zdarzenie 'blad' w cb",
            not stop_plik.exists() and cbw.koniec[-1][:2] == ("powrot", "blad"), f"{cbw.koniec}")
    cbw.poz = (33130, 31790, 5)           # piętro bez żadnego punktu planu: ucieczka PK nie startuje (cb ucieka awaryjnie)
    sprawdz("12e poza planami PK start_pk zwraca False bez skutków ubocznych (bez odłożenia wypraw)",
            not w.start_pk("ucieczka", 20.0) and w.nast_wyprawa <= 130.0 and w.w is None, f"nast={w.nast_wyprawa}")
    cbw.poz = START_E
    w2 = W.Wyprawa(cbw, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / "wp_stan2.json",
                   plik_sklepow=TMP / "wp_sklepy.json", plik_npc=TMP / "wp_npc.json", plik_stop=stop_plik,
                   czas=lambda: 5_000_000.0)
    d_zwykla = {"powody": ["glod"], "zapas": 0, "blanki": None, "zloto": 100, "cap": 100, "hp": 90, "pochodnie": None, "depo": True}
    sprawdz("12f zwykła wyprawa do depo (głód) na Edron startuje z planu 'edron' (16.10: depo każdego spotu ma swój plan)",
            w2._start_wyprawa("depo:glod", d_zwykla, 0.0) is True and w2.w is not None and w2.w["baza"] == "edron"
            and w2.w["potrzeby"] == {"depo": True} and "pk" not in w2.w["potrzeby"],
            f"nast={w2.nast_wyprawa} w={w2.w and w2.w['baza']} {logi[-2:]}")
    sprawdz("12g depo Edron z WYPRAWA_DEPO_POWROT=1: powrót nagraną trasą depo -> łowisko (a nie depo Thais)",
            bool(w2.w and w2.w["powrot"]) and w2.w["powrot"] != w2.w["legs"][0],
            f"powrot={bool(w2.w and w2.w['powrot'])}")
else:
    print("brak pliku mapy, pomijam część 12 (plan Edron)")

# 13. integracja: prawdziwy Cavebot + prawdziwa Wyprawa + plan Edron z plików tras (ruch strzałkami po atrapie świata)
if _mapa.PLIK_MAPY.is_file():
    import wypad as _wypad

    class OpsE:
        def __init__(o):
            o.uzycia = []

        def wiadomosci(o):
            return []

        def plecak(o):
            return None

        def ekwipunek(o):
            return {}

        def uzyj_pole(o, *a):
            o.uzycia.append(a)

        uzyj_line = uzyj_lopate = uzyj_pole

    s = Swiat([(0, 100, []), (3, 100, [gr("Brezniev Leonid", 2, 0)]), (4, 80, [gr("Brezniev Leonid", 1, 0)]), (5, 80, [])])
    s.poz = [33117, 31775, 8]
    b = zrob(s, wyprawa=False, mapa=MAPA)
    ops = OpsE()
    logi_w = []
    b.wyprawa = W.Wyprawa(b, ops, konf=cavebot, log=logi_w.append, plik_stanu=TMP / "int_stan.json",
                          plik_sklepow=TMP / "int_sk.json", plik_npc=TMP / "int_npc.json", plik_stop=TMP / "int_STOP",
                          czas=lambda: s.t)
    stany = []
    for t in range(0, 20):
        s.t = float(t)
        b.tick()
        stany.append(str(b.stan))
    sprawdz("13 atak PK na pętli Edron: wyprawa PK ruszyła (baza edron, potrzeby pk=ucieczka), wypad aktywny",
            b.pk_stan == "UCIECZKA" and not b.pk_fallback and b.wyprawa.w is not None and b.wypad_aktywny
            and b.wyprawa.w["potrzeby"] == {"depo": True, "pk": "ucieczka"} and b.wyprawa.w["baza"] == "edron",
            f"{b.pk_stan} fb={b.pk_fallback} w={b.wyprawa.w and b.wyprawa.w['potrzeby']}")
    sprawdz("13a marsz do depo idzie po planie (stan WYPAD), nie w UCIECZKA po trasie ani GRACZ",
            "WYPAD" in stany and "GRACZ" not in stany and "UCIECZKA" not in stany and not b.ucieczka, f"{set(stany)}")
    sprawdz("13b bot dochodzi do liny z planu (33117,31774) i próbuje wejść (uzyj_pole)", ops.uzycia and tuple(s.poz) == (33117, 31774, 8),
            f"poz={s.poz} uzycia={ops.uzycia[:1]}")
    sprawdz("13c po drodze brak plików STOP i brak wyjątków wypadu", not (TMP / "int_STOP").exists()
            and not any("wypad: błąd" in l for l in cavelog))

# --- poprawki po przeglądzie (A-F, CLI) ---
import czaszka

# A. POWROT: trasa przerwana z zewnątrz (Wypad.przerwij: w=None, wypad_aktywny=False) bez zdarzenia końca -> z powrotem DEPO
s = Swiat([(0, 100, [])])
b = zrob(s, wrogowie=TMP / "wr-A.json")
b.pk_stan = "POWROT"
b.fw.w, b.wypad_aktywny = None, False
s.t = 5.0
b.tick()
sprawdz("A POWROT przerwany z zewnątrz (w=None): wraca do DEPO i liczy nieudaną próbę", b.pk_stan == "DEPO" and b.pk_powrot_proby == 1,
        f"{b.pk_stan} proby={b.pk_powrot_proby}")
b.pk_wrogowie.karencja_do = 0.0
s.t = 100.0
b.tick()
sprawdz("A1 po przerwie 30 s ponowna próba powrotu", b.pk_stan == "POWROT" and [w[0] for w in b.fw.wywolania] == ["powrot"],
        f"{b.pk_stan} {b.fw.wywolania}")
b.pk_stan, b.pk_powrot_proby = "DEPO", 3
stop_plik = TMP / "STOP-A"
bot_stop0 = bot.STOP
bot.STOP = stop_plik
b.pk_wrogowie.karencja_do = 0.0
s.t = 300.0
b.tick()
bot.STOP = bot_stop0
sprawdz("A2 po PK_POWROT_PROBY nieudanych powrotach STOP + powiadomienie krytyczne", stop_plik.exists()
        and any(k == "pk_stop" for _, _, k in b.powiadomienia), f"{stop_plik.exists()} {b.powiadomienia}")

# B. potwór bił i zginął, po 2 s przechodzień obok: to nie PK; po oknie PK_OKNO_S znów działa; w liście tylko najbliższy
s = Swiat([(0, 100, [troll(1, 1, 0)]), (1, 80, [troll(1, 1, 0)]), (2, 80, []), (3, 80, [gr("Przechodzien", 1, 0)]),
           (4, 80, [gr("Przechodzien", 1, 0)])])
b = zrob(s, wrogowie=TMP / "wr-B.json")
sprawdz("B troll bił (HP 100->80) i zginął, po 2 s przechodzień obok: NIE PK", odtworz(b, s, 0, 4) is None and not b.pk_wrogowie.dane,
        f"{b.pk_wrogowie.dane}")
s = Swiat([(0, 100, [troll(1, 1, 0)]), (1, 80, [troll(1, 1, 0)]), (2, 80, []), (3, 80, []), (8, 80, [gr("Przechodzien", 1, 0)]),
           (9, 60, [gr("Przechodzien", 1, 0)])])
b = zrob(s, wrogowie=TMP / "wr-B2.json")
sprawdz("B1 po upływie okna od potwora nowy cios gracza obok = PK", odtworz(b, s, 0, 9) == 9)
cavebot.PK_ODL = 2
s = Swiat([(0, 100, []), (1, 70, [gr("Napastnik", 1, 0), gr("Gapiowicz", 2, 1)])])
b = zrob(s, wrogowie=TMP / "wr-B3.json")
odtworz(b, s, 0, 1)
cavebot.PK_ODL = 1
sprawdz("B2 na liście wrogów tylko najbliższy gracz (napastnik), nie każdy w PK_ODL",
        set(v["nick"] for v in b.pk_wrogowie.dane.values()) == {"Napastnik"}, f"{b.pk_wrogowie.dane.keys()}")

# C. groźna czaszka (Haiku, czaszka.py): ucieczka PK zamiast pauzy GRACZ, nick na liście wrogów
czaszka.wyczysc()
czaszka.ustaw("Skuller", "biala", 600)
s = Swiat([(0, 100, [gr("Skuller", 5, 2)]), (1, 100, [gr("Skuller", 4, 2)])])
b = zrob(s, wrogowie=TMP / "wr-C.json")
pierwsze = odtworz(b, s, 0, 1)
sprawdz("C biała czaszka w widoku (HP 100%, daleko): ucieczka PK od razu (w obiegu, w którym ją zobaczyliśmy), nie stan GRACZ",
        pierwsze == 0 and str(b.stan) != "GRACZ"
        and b.fw.wywolania[:1] == [("ucieczka", 0.0)], f"{pierwsze} {b.stan} {b.fw.wywolania}")
sprawdz("C1 nick z czaszką na liście wrogów z powodem 'czaszka', alarm poszedł",
        b.pk_wrogowie.dane.get("skuller", {}).get("powod") == "czaszka" and s.alarmy, f"{b.pk_wrogowie.dane} {s.alarmy}")
czaszka.wyczysc()
czaszka.ustaw("Czysty", "brak", 600)
s = Swiat([(0, 100, [gr("Czysty", 3, 1)]), (1, 100, [gr("Czysty", 2, 1)])])
b = zrob(s, wrogowie=TMP / "wr-C2.json")
sprawdz("C2 odczyt 'brak czaszki' / brak odczytu: bez ucieczki", odtworz(b, s, 0, 1) is None)
czaszka.wyczysc()
cavebot.PK_OBRONA = 0
czaszka.ustaw("Skuller", "czerwona", 600)
s = Swiat([(0, 100, [gr("Skuller", 5, 2)])])
b = zrob(s, wrogowie=TMP / "wr-C3.json")
odtworz(b, s, 0, 0)
cavebot.PK_OBRONA = 1
sprawdz("C3 PK_OBRONA=0: zostaje dawny stan GRACZ dla groźnego gracza", str(b.stan) == "GRACZ" and b.pk_stan is None, f"{b.stan}")
czaszka.wyczysc()

# D. restart w karencji: czekamy zamiast wracać na spot, po karencji koniec obrony bez trasy powrotnej
plikD = TMP / "wr-D.json"
plikD.write_text(json.dumps({"wrogowie": {"x": {"nick": "X", "od": 0, "ost": 0, "ile": 1}}, "karencja_do": 1000.0}))
s = Swiat([(0, 100, [])])
b = zrob(s, wrogowie=plikD)
b.pk_wrogowie.czas = s.zegar
s.t = 10.0
b.tick()
sprawdz("D start w karencji: stan DEPO (czekanie), bez wyprawy, powiadomienie", b.pk_stan == "DEPO" and b.pk_start_wait
        and not b.fw.wywolania, f"{b.pk_stan} {b.stan}")
s.t = 500.0
b.tick()
sprawdz("D1 w trakcie karencji nadal czeka (stan PAUZA_PK)", b.pk_stan == "DEPO" and str(b.stan) == "PAUZA_PK")
s.t = 1001.0
b.tick()
sprawdz("D2 po karencji koniec obrony, bez trasy powrotnej z depo", b.pk_stan is None and not b.fw.wywolania, f"{b.pk_stan} {b.fw.wywolania}")

# D3 (recenzja 15.10): restart w karencji POZA depo (np. w jaskini po awarii): ucieczka do depo, nie stanie bez obrony
plikD3 = TMP / "wr-D3.json"
plikD3.write_text(json.dumps({"wrogowie": {"x": {"nick": "X", "od": 0, "ost": 0, "ile": 1}}, "karencja_do": 1000.0}))
s = Swiat([(0, 100, [])])
b = zrob(s, wrogowie=plikD3)
b.pk_wrogowie.czas = s.zegar
b.fw.depo = (JA[0] + 40, JA[1], JA[2])
s.t = 10.0
b.tick()
sprawdz("D3 start w karencji z dala od depo: ucieczka PK do depo (start_pk), nie czekanie w miejscu",
        b.pk_stan == "UCIECZKA" and b.fw.wywolania[:1] == [("ucieczka", 10.0)], f"{b.pk_stan} {b.fw.wywolania}")

# E. przedłużanie karencji nie pisze pliku co obieg
w = obrona_pk.Wrogowie(TMP / "wr-E.json", czas=lambda: tE[0], log=lambda t: None)
tE = [1000.0]
zapisy = []
_z0 = w.zapisz
w.zapisz = lambda: (zapisy.append(1), _z0())[1]
for i in range(40):
    tE[0] = 1000.0 + i
    w.przedluz_karencje(30)
sprawdz("E 40 przedłużeń w 40 s: jeden zapis na dysk (próg 60 s)", len(zapisy) == 1, f"{len(zapisy)}")
tE[0] = 1000.0 + 61
w.przedluz_karencje(30)
sprawdz("E1 po >= 60 s przedłużenia kolejny zapis", len(zapisy) == 2 and w.karencja_do == tE[0] + 1800, f"{len(zapisy)}")

# F. DEPO bez regeneracji HP: po PK_DEPO_MAX_MIN STOP + powiadomienie
s = Swiat([(0, 40, [])])
b = zrob(s, wrogowie=TMP / "wr-F.json")
b.pk_stan, b.pk_start_wait = "DEPO", False
b.jedzenie_potrzebne = lambda g, t, p: False
stop_plik = TMP / "STOP-F"
bot.STOP = stop_plik
b.pk_wrogowie.karencja_do = 0.0
for t in (0.0, 600.0, 1100.0):
    s.t = t
    b.tick()
nie_jeszcze = stop_plik.exists()
s.t = 1300.0
b.tick()
bot.STOP = bot_stop0
sprawdz("F HP nie rośnie w depo: przed 20 min bez STOP, po 20 min STOP + powiadomienie", not nie_jeszcze and stop_plik.exists()
        and any(k == "pk_depo_hp" for _, _, k in b.powiadomienia), f"{nie_jeszcze} {stop_plik.exists()}")

# G. CLI i odświeżanie pliku działającego bota
plikG = TMP / "wr-G.json"
wG = obrona_pk.Wrogowie(plikG, czas=lambda: 5000.0, log=lambda t: None)
wG.dodaj("Zly Gracz", "atak", (1, 2, 3))
wG.dodaj("Inny", "czaszka", (1, 2, 3))
import io
import contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    r1 = obrona_pk.main(["--plik", str(plikG), "--lista"])
sprawdz("G CLI --lista pokazuje wrogów", r1 == 0 and "Zly Gracz" in buf.getvalue() and "Inny" in buf.getvalue(), buf.getvalue())
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    r2 = obrona_pk.main(["--plik", str(plikG), "--usun", "zly  gracz"])
d = json.loads(plikG.read_text())
sprawdz("G1 CLI --usun usuwa nick (bez wielkości liter), brak nicku = kod 1",
        r2 == 0 and "zly gracz" not in d["wrogowie"] and "inny" in d["wrogowie"]
        and obrona_pk.main(["--plik", str(plikG), "--usun", "nie ma"]) == 1)
import os as _os2
_os2.utime(plikG, (1, 1))                                   # inny mtime niż zapamiętany (zmiana z zewnątrz)
wG.odswiez()
sprawdz("G2 działający bot odczytuje zmianę pliku (odswiez) i nie przywraca usuniętego", not wG.znany("Zly Gracz") and wG.znany("Inny"))

print()
print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
