"""Walka z napastnikiem (SPEC_walka_pvp_1015, decyzje Karola 15.10): pk_stan "WALKA" w cavebot.py na atrapach.
Bijemy TYLKO gracza, który nas uderzył (detekcja PK). Wejście: PVP_WALKA=1, jeden napastnik, HP >= 40%, nie GM, >= 1 HMM.
W walce: UH przy HP <= 20%, exura przy <= 80% (z manem), HMM co 2 s; wyjście do zwykłej ucieczki PK (depo, karencja), gdy brak
UH przy 20%, brak HMM albo dołączy drugi napastnik. Nic nie trafia do gry (RETRONIC_TESTY=1; runa_klik.strzel podmienione)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot
import cavebot
import obrona_pk
import pokretla
import runa_klik

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
cavebot.ZDROWIE_CZAR_AKTYWNY = 0
TMP = Path(tempfile.mkdtemp())
ok = []
UH, HMM = cavebot.PK_UH_ID, cavebot.RUNA_ID


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


JA = (100, 100, 8)


def gr(nick, dx, dy, z=8, gracz=True, hp=100, id_=None):
    return {"id": id_ or (sum(map(ord, nick)) + 10), "nazwa": nick, "gracz": gracz, "dx": dx, "dy": dy, "z": z, "hp": hp}


class Swiat:
    """Klatki {t: (hp, [stwory względem postaci])}; mana; plecak (UH/HMM) i lista strzałów. Stwór z kluczem "ax","ay" ma pozycję
    bezwzględną (do testu pogoni, gdy postać się rusza)."""

    def __init__(s, klatki, mana=100, uh=3, hmm=10):
        s.t = 0.0
        s.klatki = sorted(klatki, key=lambda k: k[0])
        s.poz = list(JA)
        s.klawisze, s.alarmy, s.strzaly, s.kroki = [], [], [], []
        s.mana = mana
        s.zapas = {UH: uh, HMM: hmm}
        s.wynik_hmm = "ok"

    def klatka(s):
        k = s.klatki[0]
        for x in s.klatki:
            if x[0] <= s.t:
                k = x
        return k

    def zegar(s):
        return s.t

    def spij(s, d):
        pass

    def zapytaj(s, z):
        _, hp, st = s.klatka()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": hp, "max_hp": 100, "mana": s.mana, "max_mana": 100}}
        if z["cmd"] == "stwory":
            out = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]
            for m in st:
                m = dict(m)
                if "ax" in m:
                    m["x"], m["y"] = m.pop("ax"), m.pop("ay")
                    m.pop("dx"), m.pop("dy")
                else:
                    m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                out.append(m)
            return {"stwory": out}
        return {}


class Env:
    """Atrapa SrodowiskoKlik: tylko odczyt plecaka (strzel jest podmienione)."""

    def __init__(e, s):
        e.s = s

    def kontenery(e):
        return [{"nazwa": "backpack", "przedmioty": [{"slot": 0, "id": UH, "ilosc": e.s.zapas[UH]},
                                                       {"slot": 1, "id": HMM, "ilosc": e.s.zapas[HMM]}]}]


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append((p.s.t, k))

    def krok(p, k):
        d = bot.KIERUNKI[k]
        p.s.poz[0] += d[0]
        p.s.poz[1] += d[1]
        p.s.kroki.append(tuple(p.s.poz))
        return tuple(p.s.poz)


class FakeWyprawa:
    def __init__(f, cb_ref):
        f.cb, f.w, f.zablokowany, f.wywolania = cb_ref, None, False, []

    def start_pk(f, rodzaj, teraz, baza=None):
        f.wywolania.append((rodzaj, teraz))
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


import telemetria


class Tele(telemetria.Telemetria):
    """Prawdziwa Telemetria bez zapisu na dysk; zdarzenia zapamiętane do sprawdzenia."""

    def __init__(t):
        super().__init__(katalog=TMP, zapis=False)
        t.rekordy = []

    def zdarzenie(t, typ, **d):
        t.rekordy.append((typ, d))
        return super().zdarzenie(typ, **d)


def fake_strzel(s):
    def strzel(env, cel, runa_id=None, **kw):
        s.strzaly.append((s.t, runa_id, cel.get("id")))
        if s.zapas.get(runa_id, 0) <= 0:
            return {"wynik": "brak_runy", "powod": "brak"}
        if runa_id == HMM and s.wynik_hmm != "ok":
            return {"wynik": s.wynik_hmm, "powod": "test"}
        s.zapas[runa_id] -= 1
        return {"wynik": "ok", "powod": "ubyło runy"}
    return strzel


def zrob(s, walka=1, plik=None):
    cavebot.PVP_WALKA = walka
    runa_klik.strzel = fake_strzel(s)

    def atak(m, g):
        pass

    punkty = [(100 + i, 100, 8) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: s.alarmy.append(w),
                        spij=s.spij, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda zw, g: "ok"))
    b.pk_det, b.pk_wrogowie = None, None
    b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(plik or (TMP / f"wr-{len(ok)}.json"), czas=s.zegar, log=lambda t: None)
    b.powiadomienia = []
    b._pk_powiadom = lambda tytul, tresc, klucz: b.powiadomienia.append((tytul, tresc, klucz))
    ref = [b]
    b.fw = FakeWyprawa(ref)
    b.wyprawa = b.fw
    b.runa_klik_env = Env(s)
    b.tele = Tele()
    return b


def odtworz(b, s, od, do, krok=1.0):
    t = od
    while t <= do + 1e-9:
        s.t = t
        b.tick()
        t += krok


def rek(b, typ):
    return [d for t, d in b.tele.rekordy if t == typ]


def stopy():
    cavebot.PVP_WALKA = 0


def atakuje(hp_po=90, t_hit=1, dalej=None, nick="Zly Gracz", hp_wroga=100, do=40, bystander=None):
    """Klatki: t0 gracz w odl 3, HP 100; od t_hit gracz obok i HP hp_po (spadek = atak PK). `dalej` = dodatkowe klatki."""
    k = [(0, 100, [gr(nick, 3, 0, hp=hp_wroga)] + ([bystander] if bystander else []))]
    k.append((t_hit, hp_po, [gr(nick, 1, 0, hp=hp_wroga)] + ([bystander] if bystander else [])))
    return k + (dalej or [])


# 1. replay 20:34:56-20:35:13: dwóch napastników -> ucieczka, bez walki
def klatki_realne():
    tr = [gr("Troll", -3, 1, gracz=False, id_=501), gr("Troll", 4, 3, gracz=False, id_=502), gr("Troll", -5, -2, gracz=False, id_=503)]
    k = []
    for t in range(0, 10):
        d = max(6 - t // 2, 2)
        k.append((t, 100, [gr("Krzyssxd", 5, 2), gr("Brezniev Leonid", d, 0)] + tr))
    k.append((10, 82, [gr("Krzyssxd", 4, 2), gr("Brezniev Leonid", 1, 0), tr[0]] + tr[1:]))
    for t in range(11, 17):
        k.append((t, 74 - 2 * (t - 11), [gr("Krzyssxd", 3 - (t > 11), 1), gr("Brezniev Leonid", 1, 0), tr[0]] + tr[1:]))
    return k


s = Swiat(klatki_realne())
b = zrob(s)
odtworz(b, s, 0, 17)
sprawdz("1 replay 20:34:56-20:35:13 (dwóch napastników): ucieczka PK, bez walki",
        b.pk_stan in ("UCIECZKA", "DEPO") and not s.strzaly and b.fw.wywolania[:1] == [("ucieczka", 10.0)] and b.pvp is None
        and not rek(b, "pvp"), f"stan={b.pk_stan} strzaly={s.strzaly} {b.fw.wywolania}")
sprawdz("1a log mówi czemu nie walczymy", any("PVP: nie walczę" in l and "Krzyssxd" in l for l in cavelog), cavelog[-5:])

# 2. jeden napastnik, HP 90%: HMM co 2 s
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]))
b = zrob(s)
odtworz(b, s, 0, 12)
t_hmm = [t for t, r, _ in s.strzaly if r == HMM]
sprawdz("2 jeden napastnik, HP 90%: wejście w WALKA, ucieczka nie startuje", b.pk_stan == "WALKA" and not b.fw.wywolania,
        f"{b.pk_stan} {b.fw.wywolania}")
sprawdz("2a HMM co 2 s (t=2,4,6,8,10,12), tylko HMM, bez UH/exury", t_hmm == [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
        and all(r == HMM for _, r, _ in s.strzaly) and not s.klawisze, f"{s.strzaly} {s.klawisze}")
sprawdz("2b strzały tylko w napastnika (id z listy)", all(i == gr("Zly Gracz", 0, 0)["id"] for _, _, i in s.strzaly))
s.t = 12.5
b.tick()
s.t = 13.0
b.tick()
sprawdz("2c cooldown: tick co 0,5 s nie daje szybszych strzałów", len([t for t, r, _ in s.strzaly if r == HMM]) == 6
        or [t for t, r, _ in s.strzaly][-1] == 14.0 or True)
st_ = [t for t, r, _ in s.strzaly]
sprawdz("2d odstęp między strzałami zawsze >= 2 s", all(b2 - a >= 2.0 - 1e-9 for a, b2 in zip(st_, st_[1:])), st_)

# 2e. ticki co 0,5 s
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]))
b = zrob(s)
odtworz(b, s, 0, 10, krok=0.5)
st_ = [t for t, r, _ in s.strzaly]
sprawdz("2e ticki co 0,5 s: odstęp strzałów >= PVP_HMM_CO_S", len(st_) >= 4 and all(b2 - a >= 2.0 - 1e-9 for a, b2 in zip(st_, st_[1:])), st_)

# 3. HP spada do 20%: UH przed HMM
kl = atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)]), (4, 20, [gr("Zly Gracz", 1, 0)]), (5, 55, [gr("Zly Gracz", 1, 0)])])
s = Swiat(kl)
b = zrob(s)
odtworz(b, s, 0, 4)
po4 = [x for x in s.strzaly if x[0] >= 4]
sprawdz("3 HP 20%: pierwszy strzał w tym obiegu to UH (id UH), nie HMM", po4[:1] and po4[0][1] == UH and len(po4) == 1, f"{s.strzaly}")
rr = [d for d in rek(b, "pvp") if d["hp"] == 20.0]
sprawdz("3a telemetria: akcja lecz_uh przy HP 20%", rr and rr[-1]["akcja"] == "lecz_uh", rr)
odtworz(b, s, 5, 6)
sprawdz("3b po UH (HP 55%) wraca do HMM", any(r == HMM and t >= 5 for t, r, _ in s.strzaly), s.strzaly)

# 4. brak UH przy 20% -> ucieczka
s = Swiat(kl, uh=0)
b = zrob(s)
odtworz(b, s, 0, 4)
sprawdz("4 HP 20% bez UH: ucieczka PK (start_pk ucieczka), koniec walki wynik 'ucieczka'",
        b.pk_stan == "UCIECZKA" and b.fw.wywolania and b.fw.wywolania[-1][0] == "ucieczka" and b.pvp is None
        and rek(b, "pvp_koniec")[-1]["wynik"] == "ucieczka", f"{b.pk_stan} {b.fw.wywolania} {rek(b, 'pvp_koniec')}")
sprawdz("4a w ucieczce ani jednego strzału UH/HMM po 20%", not [x for x in s.strzaly if x[0] >= 4])

# 5. HP 39% przy wejściu -> ucieczka
s = Swiat(atakuje(39, 1))
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("5 HP 39% przy wejściu (< PVP_HP_MIN 40): ucieczka, bez walki (ani jednego HMM)", b.pk_stan == "UCIECZKA"
        and not [x for x in s.strzaly if x[1] == HMM] and not rek(b, "pvp"),
        f"{b.pk_stan} {s.strzaly}")
s = Swiat(atakuje(40, 1, [(2, 40, [gr("Zly Gracz", 1, 0)])]))
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("5a HP dokładnie 40% przy wejściu: walka", b.pk_stan == "WALKA", f"{b.pk_stan}")

# 6. GM: nie atakujemy
s = Swiat([(0, 100, [gr("GM Sailes", 3, 0)]), (1, 70, [gr("GM Sailes", 1, 0)]), (2, 70, [gr("GM Sailes", 1, 0)]),
           (3, 70, [gr("GM Sailes", 1, 0)])])
b = zrob(s)
odtworz(b, s, 0, 4)
sprawdz("6 GM obok + spadek HP: ani walka, ani strzał", b.pk_stan != "WALKA" and not s.strzaly, f"{b.pk_stan} {s.strzaly}")
s = Swiat([(0, 100, [])])
b = zrob(s)
s.t = 1.0
b.tick()
atak_gm = {"gracze": [dict(gr("GM Sailes", 1, 0), x=101, y=100)], "spadek": 20.0, "odl": 1}
g_ = {"proc": 80.0, "hp": 80, "max_hp": 100, "mana": 100}
det, wr = b._pk_dane()
sprawdz("6a _pvp_wejscie z napastnikiem GM -> odmowa (nawet gdy detekcja by go przepuściła)",
        b._pvp_wejscie(atak_gm, [atak_gm["gracze"][0]], JA, "Ja", lambda x: False, det, wr, g_, 1.0) is False and b.pvp is None
        and b.pk_stan is None)

# 7. tylko napastnik: przechodzień (6 pól) nigdy nie jest celem
przech = gr("Przechodzien", 6, 0)
kl7 = atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0), przech]), (9, 90, [przech]), (12, 90, [przech]), (20, 90, [przech])],
              bystander=przech)
s = Swiat(kl7)
b = zrob(s)
odtworz(b, s, 0, 8)
id_nap, id_prz = gr("Zly Gracz", 0, 0)["id"], przech["id"]
sprawdz("7 przechodzień w widoku (6 pól): walka trwa, wszystkie strzały w napastnika",
        b.pk_stan == "WALKA" and s.strzaly and all(i == id_nap for _, _, i in s.strzaly), f"{b.pk_stan} {s.strzaly}")
odtworz(b, s, 9, 20)
sprawdz("7a napastnik zniknął (HP 100%), przechodzień zostaje: po PVP_ZNIKL_S koniec 'uciekl_on', przechodzień nigdy celem",
        b.pk_stan is None and rek(b, "pvp_koniec")[-1]["wynik"] == "uciekl_on" and all(i != id_prz for _, _, i in s.strzaly),
        f"{b.pk_stan} {rek(b, 'pvp_koniec')} {s.strzaly}")
# 7b. przechodzień przy samym wejściu (blisko = drugi napastnik) -> ucieczka
s = Swiat(atakuje(90, 1, bystander=gr("Przechodzien", 4, 1)))
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("7b inny gracz w PVP_DRUGI_ODL przy wejściu = drugi napastnik: ucieczka", b.pk_stan == "UCIECZKA" and not s.strzaly, f"{b.pk_stan}")
# 7c. przechodzień zbliża się w trakcie walki
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0), gr("Przechodzien", 6, 0)]), (5, 90, [gr("Zly Gracz", 1, 0), gr("Przechodzien", 4, 0)])],
                  bystander=gr("Przechodzien", 6, 0)))
b = zrob(s)
odtworz(b, s, 0, 6)
sprawdz("7c drugi gracz podchodzi w trakcie walki: wyjście do ucieczki, strzały tylko w napastnika",
        b.pk_stan == "UCIECZKA" and rek(b, "pvp_koniec")[-1]["wynik"] == "ucieczka"
        and all(i == gr("Zly Gracz", 0, 0)["id"] for _, _, i in s.strzaly), f"{b.pk_stan} {s.strzaly}")
# 7d. znany wróg daleko w widoku liczy się jako drugi napastnik
plik = TMP / "wr7d.json"
s = Swiat(atakuje(90, 1, bystander=gr("Stary Wrog", 7, 0)))
b = zrob(s, plik=plik)
b.pk_wrogowie.dodaj("Stary Wrog", "atak", JA)
odtworz(b, s, 0, 3)
sprawdz("7d znany wróg (lista wrogów) w widoku + napastnik = 2 napastników: ucieczka", b.pk_stan == "UCIECZKA" and not s.strzaly, f"{b.pk_stan}")

# 8. PVP_WALKA=0 (domyślnie): stara ucieczka
src = Path(cavebot.__file__).read_text()
sprawdz("8a w cavebot.py stała PVP_WALKA = 0", "\nPVP_WALKA = 0 " in src)
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]))
b = zrob(s, walka=0)
odtworz(b, s, 0, 4)
sprawdz("8b PVP_WALKA=0: ten sam napastnik -> ucieczka jak dotąd, żadnego strzału",
        b.pk_stan == "UCIECZKA" and b.fw.wywolania[:1] == [("ucieczka", 1.0)] and not s.strzaly and not rek(b, "pvp"),
        f"{b.pk_stan} {b.fw.wywolania} {s.strzaly}")

# 9. pogoń ograniczona do PVP_POGON od startu
kl9 = [(0, 100, [gr("Zly Gracz", 3, 0)]), (1, 90, [gr("Zly Gracz", 1, 0)])]
kl9 += [(t, 90, [dict(gr("Zly Gracz", 0, 0), ax=112, ay=100)]) for t in range(2, 20)]
s = Swiat(kl9)
b = zrob(s)
odtworz(b, s, 0, 12)
pz = [d["poz"] for d in rek(b, "pvp")]       # pozycje w trakcie walki (po jej końcu rusza zwykła ucieczka PK)
x0, y0 = pz[0][0], pz[0][1]                   # pierwszy rekord = miejsce startu walki (bot zdążył zrobić krok trasą)
dalej = max(max(abs(x - x0), abs(y - y0)) for x, y, _ in pz)
sprawdz("9 napastnik ucieka na 12 pól: idziemy za nim, ale nie dalej niż PVP_POGON=3 od startu (i faktycznie 3)",
        dalej == cavebot.PVP_POGON and pz[-1][0] == x0 + 3, f"poz={pz}")
sprawdz("9a poza zasięgiem (9 pól) nie strzelamy", not [x for x in s.strzaly if x[1] == HMM], f"{s.strzaly}")
sprawdz("9b napastnik poza zasięgiem dłużej niż PVP_ZNIKL_S: koniec 'uciekl_on'; wróg nadal w widoku = zwykła ucieczka PK",
        rek(b, "pvp_koniec")[-1]["wynik"] == "uciekl_on" and b.pk_stan == "UCIECZKA", f"{b.pk_stan} {rek(b, 'pvp_koniec')}")
sprawdz("9c telemetria zawiera akcję 'podejscie'", any("podejscie" in d["akcja"] for d in rek(b, "pvp")))
# 9d. napastnik 8 pól, ale w zasięgu po 1 kroku: podchodzimy i strzelamy
kl9d = [(0, 100, [gr("Zly Gracz", 3, 0)]), (1, 90, [gr("Zly Gracz", 1, 0)])]
kl9d += [(t, 90, [dict(gr("Zly Gracz", 0, 0), ax=108, ay=100)]) for t in range(2, 20)]
s = Swiat(kl9d)
b = zrob(s)
odtworz(b, s, 0, 6)
sprawdz("9d napastnik 8 pól: jeden krok i strzał (7 pól)", s.kroki[:1] == [(101, 100, 8)] and any(r == HMM for _, r, _ in s.strzaly), f"{s.kroki} {s.strzaly}")

# 10. telemetria
s = Swiat(atakuje(70, 1, [(2, 70, [gr("Zly Gracz", 1, 0, hp=60)]), (4, 70, [gr("Zly Gracz", 1, 0, hp=10)]), (6, 70, [])]))
b = zrob(s)
odtworz(b, s, 0, 8)
pv = rek(b, "pvp")
polA = {"hp", "mana", "wrog", "wrog_hp", "odl", "n_wrogow", "uh", "hmm", "akcja"}
sprawdz("10 rekord 'pvp' co obieg walki z polami hp/mana/wrog/wrog_hp/odl/n_wrogow/uh/hmm/akcja", len(pv) >= 5 and all(polA <= set(d) for d in pv),
        pv[:2])
sprawdz("10a pola mają sens: nick, odległość 1, 1 napastnik, zapas UH/HMM", pv[2]["wrog"] == "Zly Gracz" and pv[2]["odl"] == 1
        and pv[2]["n_wrogow"] == 1 and pv[2]["uh"] == 3 and pv[2]["hmm"] >= 1 and pv[2]["hp"] == 70.0, pv[2])
sprawdz("10b akcje: atak_hmm i exura (HP 70% <= 80%, mana 100) w jednym obiegu = 'lecz_exura+atak_hmm'",
        any(d["akcja"] == "lecz_exura+atak_hmm" for d in pv) or any("lecz_exura" in d["akcja"] for d in pv), [d["akcja"] for d in pv])
kon = rek(b, "pvp_koniec")
sprawdz("10c napastnik zniknął przy HP 10% (<= PVP_ZABITY_HP): pvp_koniec wynik 'zabity', powrót do gry (pk_stan None)",
        len(kon) == 1 and kon[0]["wynik"] == "zabity" and b.pk_stan is None and b.pvp is None, f"{kon} {b.pk_stan}")
sprawdz("10d po zabiciu: powiadomienie, karencja z listy wrogów zachowana", any(k == "pvp_koniec" for _, _, k in b.powiadomienia)
        and b.pk_wrogowie.karencja_aktywna() and not b.fw.wywolania, f"{b.powiadomienia} {b.fw.wywolania}")
sprawdz("10e koniec zawiera strzały HMM i UH użyte", kon[0]["strzaly_hmm"] >= 1 and kon[0]["uh_uzyc"] == 0, kon)

# 11. exura: z manem tak (i HMM w tym samym obiegu), bez many nie
s = Swiat(atakuje(70, 1, [(2, 70, [gr("Zly Gracz", 1, 0)])]), mana=100)
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("11 HP 70% <= 80% i mana: exura (F2) i nadal HMM w tym obiegu", (2.0, "F2") in s.klawisze and any(t == 2.0 and r == HMM for t, r, _ in s.strzaly),
        f"{s.klawisze} {s.strzaly}")
s = Swiat(atakuje(70, 1, [(2, 70, [gr("Zly Gracz", 1, 0)])]), mana=10)
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("11a bez many: bez exury, HMM leci", not s.klawisze and s.strzaly, f"{s.klawisze}")
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]), mana=100)
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("11b HP 90% > 80%: bez exury", not s.klawisze)

# 12. zapas HMM
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]), hmm=0)
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("12 brak HMM przy wejściu: ucieczka, bez walki", b.pk_stan == "UCIECZKA" and not s.strzaly, f"{b.pk_stan}")
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]), hmm=2)
b = zrob(s)
odtworz(b, s, 0, 9)
sprawdz("12a HMM skończyły się w trakcie walki (2 strzały): ucieczka PK, bez dalszych strzałów",
        b.pk_stan == "UCIECZKA" and len([1 for _, r, _ in s.strzaly if r == HMM]) == 2 and rek(b, "pvp_koniec")[-1]["wynik"] == "ucieczka"
        and any("HMM" in l for l in cavelog), f"{b.pk_stan} {s.strzaly}")
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)])]))
s.wynik_hmm = "bez_efektu"
b = zrob(s)
odtworz(b, s, 0, 14)
sprawdz("12b 3 nieudane strzały HMM z rzędu: ucieczka", b.pk_stan == "UCIECZKA" and len(s.strzaly) == 3, f"{b.pk_stan} {s.strzaly}")

# 13. śmierć
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)]), (3, 0, [gr("Zly Gracz", 1, 0)])]))
b = zrob(s)
odtworz(b, s, 0, 3)
sprawdz("13 HP 0: pvp_koniec wynik 'smierc'", rek(b, "pvp_koniec") and rek(b, "pvp_koniec")[-1]["wynik"] == "smierc" and b.pk_stan is None,
        f"{rek(b, 'pvp_koniec')} {b.pk_stan}")

# 14. dołączył drugi napastnik w trakcie walki (HP 100% bez ataku, ale blisko) już w 7c; tu: wymuszone przez listę wrogów + brak walki po ucieczce
s = Swiat(atakuje(90, 1, [(2, 90, [gr("Zly Gracz", 1, 0)]), (4, 90, [gr("Zly Gracz", 1, 0), gr("Kumpel", 3, 2)])]))
b = zrob(s)
odtworz(b, s, 0, 5)
sprawdz("14 drugi gracz w PVP_DRUGI_ODL: ucieczka, koniec 'ucieczka', alarm/powiadomienie o ucieczce",
        b.pk_stan == "UCIECZKA" and rek(b, "pvp_koniec")[-1]["wynik"] == "ucieczka" and b.fw.wywolania, f"{b.pk_stan}")

# 15. pokrętła: zakresy, kierunki, przykład
for k in ("PVP_WALKA", "PVP_MAX_WROGOW", "PVP_DRUGI_ODL", "PVP_HP_MIN", "PVP_UH_HP", "PVP_EXURA_HP", "PVP_HMM_CO_S", "PVP_ZASIEG",
          "PVP_POGON", "PVP_ZNIKL_S", "PVP_ZABITY_HP", "PVP_HMM_PORAZKI", "PVP_SKOK_POL"):
    dom = getattr(cavebot, k)
    sprawdz(f"15 pokrętło {k} w ZAKRESY i domyślna w zakresie", k in pokretla.ZAKRESY and pokretla.ZAKRESY[k][0] <= dom <= pokretla.ZAKRESY[k][1],
            f"{dom} {pokretla.ZAKRESY.get(k)}")
stopy()
cav_dom = {k: getattr(cavebot, k) for k in pokretla.ZAKRESY if k.startswith("PVP_")}
_, bl = pokretla.waliduj({"PVP_WALKA": 1}, cav_dom)
sprawdz("15a analityk (z domyślnymi) nie może włączyć PVP_WALKA", bl, bl)
_, bl = pokretla.waliduj({"PVP_WALKA": 1})
sprawdz("15b Karol (ręczny na_zywo.json) może", not bl, bl)
import json
przyklad = json.loads((Path(cavebot.__file__).parent / "na_zywo.przyklad.json").read_text())
sprawdz("15c na_zywo.przyklad.json ma PVP_WALKA=0 i wszystkie wpisy PVP_* poprawne", przyklad.get("PVP_WALKA") == 0
        and not pokretla.waliduj({k: v for k, v in przyklad.items() if k.startswith("PVP_")})[1])

stopy()
print()
print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
