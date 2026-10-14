"""Drzwi na trasie wyprawy (etap DRZWI w wypad.py, drzwi_przystankow w wyprawa.py) na atrapach.
Świat, cavebot i operacje biorę z test_wyprawa.py (ta sama atrapa), dokładam zamknięte drzwi. Prawdziwa mapa
i prawdziwy trasy/wyprawa_sklepy.json (Frodo: drzwi (32365,32208,7)). Nic nie trafia do gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_wyprawa.py").read_text()
_src = _src[:_src.index("# --- 0. dane i pokrętła")]
_g = {"__file__": str(KAT / "testy" / "test_wyprawa.py"), "__name__": "atrapy_wyprawa"}
exec(compile(_src, "test_wyprawa(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()

cheb = wypad.cheb
DRZWI = (32365, 32208, 7)
FRODO_STOI = (32358, 32210, 7)
START_BLISKO = DO[-8]
SK = json.loads(W.PLIK_SKLEPOW.read_text())["przystanki"]
DOJ = [tuple(p) for p in SK["frodo"]["dojscie"]]
POW = [tuple(p) for p in SK["frodo"]["powrot"]]


class PostacD(Postac):
    def krok(p, k):
        s = p.s
        d = bot.KIERUNKI[k]
        n = (s.poz[0] + d[0], s.poz[1] + d[1], s.poz[2])
        if n in s.zamkniete:
            s.t += 0.2
            return None
        return Postac.krok(p, k)


class OpsD(Ops):
    def uzyj_pole(o, pole, poz):
        s = o.s
        s.t += 0.5
        pole = tuple(pole)
        if pole in s.zamkniete or pole in s.drzwi_all:
            if max(abs(s.poz[0] - pole[0]), abs(s.poz[1] - pole[1])) > 1:
                raise wypad.BrakEkranu("za daleko")
            s.uzyc += 1
            if s.otworz_od is not None and s.uzyc >= s.otworz_od:
                s.zamkniete.discard(pole)
        else:
            Ops.uzyj_pole(o, pole, poz)


def swiat(otworz_od=1, poz=START_BLISKO, **kw):
    """Świat z zamkniętymi drzwiami Frodo; otwierają się przy `otworz_od`-tym Use (None = nigdy)."""
    s = Swiat(poz=poz, jedzenie=kw.pop("jedzenie", 1), torch=5, **kw)
    s.zamkniete = {DRZWI}
    s.drzwi_all = {DRZWI}
    s.uzyc = 0
    s.otworz_od = otworz_od
    kat = s.npc["Frodo"][1]
    s.npc["Frodo"] = ((32358, 32212, 7), kat)         # NPC przy polu stania z trasy
    return s


def uruchom(s, maks=9000, fn=None, stan=None):
    cb = CB(s)
    cb.postac = PostacD(s)
    logi = []
    ops = OpsD(s)
    ops.log = logi.append
    _n[0] += 1
    w = W.Wyprawa(cb, ops, konf=Konf(), log=logi.append, plik_stanu=stan or (TMP / f"stan_d{_n[0]}.json"),
                  plik_sklepow=W.PLIK_SKLEPOW, plik_npc=TMP / f"npc_d{_n[0]}.json",
                  plik_stop=TMP / f"STOP_d{_n[0]}", czas=lambda: s.wall)
    w.logi = logi
    return cb, w


def jedz(s, cb, w, maks=9000, fn=None):
    wystartowal = False
    for i in range(maks):
        s.t += 0.3
        s.wall += 0.3
        cb.ruch_poz = tuple(s.poz)
        cb.ostatnie_stwory = []
        if fn and fn(i):
            return i, wystartowal, True
        w.tick()
        if w.aktywny:
            wystartowal = True
        elif wystartowal:
            return i, True, False
    return maks, wystartowal, False


def ruszaj(s, cb, w):
    return pre(s, cb, w)


# --- 1. budowa planu: etapy DRZWI ---------------------------------------------------------
a, b = (32366, 32208, 7), (32363, 32208, 7)
et = wypad.zbuduj_etapy([(32370, 32208, 7), a, DRZWI, b, (32360, 32208, 7)], MAPA, {DRZWI})
typy = [e["typ"] for e in et]
sprawdz("1a trasa z drzwiami: IDZ, DRZWI, IDZ", typy == ["IDZ", "DRZWI", "IDZ"], typy)
sprawdz("1b DRZWI: stoi = pole przed drzwiami, drzwi = kafelek; następny IDZ zaczyna się na drzwiach",
        et[1]["stoi"] == a and et[1]["drzwi"] == DRZWI and et[2]["punkty"][0] == DRZWI and et[0]["punkty"][-1] == a, et)
et2 = wypad.zbuduj_etapy([(32370, 32208, 7), (32367, 32208, 7), DRZWI, b], MAPA, {DRZWI})
sprawdz("1c rzadkie nagranie (stoi 2 pola od drzwi): dodane pole sąsiednie, stoi sąsiaduje z drzwiami",
        et2[1]["stoi"] == a and cheb(et2[1]["stoi"], DRZWI) == 1 if False else
        et2[1]["stoi"] == (32366, 32208, 7), et2)
sprawdz("1d drzwi znane mapie jako ściana: drzwi_z_mapy znajduje kafelek nagrany w dojscie",
        DRZWI in wypad.drzwi_z_mapy(DOJ, MAPA) and DRZWI in wypad.drzwi_z_mapy(POW, MAPA))
sprawdz("1e sprawdz_plan z drzwiami: brak uwag", not wypad.sprawdz_plan(et, MAPA, {DRZWI}), wypad.sprawdz_plan(et, MAPA, {DRZWI}))
zly = [{"typ": "IDZ", "punkty": [(1, 1, 7)]}, {"typ": "DRZWI", "stoi": (1, 1, 7), "drzwi": (5, 5, 7)}]
sprawdz("1f sprawdz_plan: drzwi niesąsiadujące ze stoi zgłoszone", len(wypad.sprawdz_plan(zly)) >= 1)

# --- 2. plan wyprawy z prawdziwego pliku ----------------------------------------------------
logr = []
problemy = W.raport(mapa=MAPA, log=logr.append)
sprawdz("2a wyprawa.py plan: bez 'frodo: brak drogi po mapie od Gorna'", not any(p.startswith("frodo: brak drogi") for p in problemy), problemy)
sprawdz("2b wyprawa.py plan: bez 'xodet: brak drogi po mapie' (drzwi Xodeta też przechodnie)",
        not any(p.startswith("xodet: brak drogi") for p in problemy), problemy)
s0 = swiat()
cb0, w0 = uruchom(s0)
potrz = {"frodo": True, "xodet": True}
wy, blad = w0._zbuduj("troll", potrz)
sprawdz("2c _zbuduj (frodo + xodet): plan zbudowany", wy is not None, blad)
if wy:
    wszystkie = [e for l in wy["legs"] for e in l] + wy["powrot"]
    dr = [e for e in wszystkie if e["typ"] == "DRZWI"]
    sprawdz("2d w planie są etapy DRZWI na (32365,32208) i (32400,32217)",
            {e["drzwi"] for e in dr} >= {DRZWI, (32400, 32217, 7)}, [e["drzwi"] for e in dr])
    sprawdz("2e każde DRZWI: stoi sąsiaduje z drzwiami", all(cheb(e["stoi"], e["drzwi"]) == 1 for e in dr), dr)
    zle = [b for n, et_ in [(f"leg{i}", l) for i, l in enumerate(wy["legs"])] + [("powrot", wy["powrot"])]
           for b in wypad.sprawdz_plan(et_, MAPA, W.drzwi_przystankow(SK, MAPA))]
    sprawdz("2f sprawdz_plan całej wyprawy: brak uwag", not zle, zle)
    sprawdz("2g w logu startu nie ma 'plan:' (blokada)", not any("plan " in l for l in w0.logi), w0.logi)

# --- 3. (a) drzwi otwierają się od 1. próby -------------------------------------------------
s = swiat(otworz_od=1)
cb, w = uruchom(s)
st_ = ruszaj(s, cb, w)
n, wyst, _ = jedz(s, cb, w)
kon = ev(s, "wyprawa_koniec")
dr_ev = [d for t, d in s.zdarzenia if t == "wypad_krok" and d.get("rodzaj") == "drzwi"]
sprawdz("3a otwarte od 1. próby: wyprawa ok, hamy kupione, pozycje koniec na z8 lub trasie powrotnej",
        st_ and wyst and kon and kon[-1]["wynik"] == "ok" and s.plecak.get(3582, 0) >= 3, (kon, s.plecak, w.logi[-4:]))
sprawdz("3a2 jedno Use, dwukrotne przejście przez drzwi (tam i z powrotem), drzwi otwarte", s.uzyc == 1 and DRZWI not in s.zamkniete
        and len(dr_ev) >= 2, (s.uzyc, len(dr_ev)))
sprawdz("3a3 dialog u Frodo odbył się (hi, buy ham, yes)", "hi" in s.mowa and any(x.endswith(" ham") for x in s.mowa) and "yes" in s.mowa, s.mowa)

# --- 4. (b) od 2. próby -----------------------------------------------------------------------
s = swiat(otworz_od=2)
cb, w = uruchom(s)
ruszaj(s, cb, w)
n, wyst, _ = jedz(s, cb, w)
kon = ev(s, "wyprawa_koniec")
sprawdz("4a drzwi otwarte od 2. Use: wyprawa ok, zakupy zrobione, 2 użycia", wyst and kon and kon[-1]["wynik"] == "ok"
        and s.plecak.get(3582, 0) >= 3 and s.uzyc == 2, (s.uzyc, kon, w.logi[-4:]))

# --- 5. (c) nigdy: błąd w skończonym czasie, bez pętli ---------------------------------------------
s = swiat(otworz_od=None)
cb, w = uruchom(s)
ruszaj(s, cb, w)
n, wyst, _ = jedz(s, cb, w, maks=3000)
kon = ev(s, "wyprawa_koniec")
bl = [d for t, d in s.zdarzenia if t == "wypad_blad" and str(d.get("rodzaj", "")).startswith("drzwi")]
sprawdz("5a drzwi nie otwierają się: wypad kończy się w < 3000 obiegów (bez pętli)", wyst and n < 3000 and not cb.wypad_aktywny, (n, wyst))
sprawdz("5b próby ograniczone: <= 3 prób (Use/krok/Use) i błąd drzwi_* zgłoszony, zakupów brak",
        s.uzyc <= wypad.DRZWI_PROB and len(bl) >= wypad.DRZWI_PROB and s.plecak.get(3582, 0) == 1 and "buy" not in " ".join(s.mowa),
        (s.uzyc, len(bl), s.plecak, s.mowa))
sprawdz("5c koniec nie jest 'ok' (bez zakupów / błąd), bot nie stoi na drzwiach", kon and kon[-1]["wynik"] != "ok" and tuple(s.poz) != DRZWI, kon)
# bez drzwi można tylko wrócić przed nimi: nie zostajemy w środku ściany
sprawdz("5d po porażce wróciliśmy na łowisko (z8) albo koniec w pobliżu trasy powrotnej", s.poz[2] in (7, 8), s.poz)

# --- 6. (d) powrót przez te same drzwi ---------------------------------------------------------------
# 6a: drzwi zostają otwarte: powrót bez ani jednego dodatkowego Use (sprawdzone w 3a2).
# 6b: drzwi zamknęły się w trakcie zakupów: powrót używa ich znowu
s = swiat(otworz_od=1)
cb, w = uruchom(s)
ruszaj(s, cb, w)
zam = {"zrobione": False}


def zamknij_po_sklepie(i):
    if not zam["zrobione"] and w.faza == "z":
        zam["zrobione"] = True
        s.zamkniete.add(DRZWI)
        zam["uzyc_przed"] = s.uzyc
    return False


n, wyst, _ = jedz(s, cb, w, fn=zamknij_po_sklepie)
kon = ev(s, "wyprawa_koniec")
sprawdz("6b drzwi zamknięte po zakupach: powrót używa ich ponownie i kończy ok", zam["zrobione"] and s.uzyc == zam["uzyc_przed"] + 1
        and kon and kon[-1]["wynik"] == "ok" and DRZWI not in s.zamkniete, (zam, s.uzyc, kon, w.logi[-4:]))
# 6c: zamknięte po zakupach i nigdy się nie otworzą: skończony błąd (alarm + STOP), bez pętli
s = swiat(otworz_od=1)
cb, w = uruchom(s)
ruszaj(s, cb, w)
zam = {"zrobione": False}


def zamknij_na_stale(i):
    if not zam["zrobione"] and w.faza == "z":
        zam["zrobione"] = True
        s.zamkniete.add(DRZWI)
        s.otworz_od = None
    return False


n, wyst, _ = jedz(s, cb, w, maks=4000, fn=zamknij_na_stale)
kon = ev(s, "wyprawa_koniec")
sprawdz("6c powrót, drzwi nie ustępują: koniec z błędem w skończonym czasie, alarm, STOP, <= 3 próby Use",
        zam["zrobione"] and n < 4000 and not cb.wypad_aktywny and kon and kon[-1]["wynik"] == "blad"
        and s.alarmy and w.zablokowany is not None and s.uzyc <= 1 + wypad.DRZWI_PROB, (n, kon, s.alarmy, s.uzyc))

# --- 7. (e) wznowienie po restarcie ------------------------------------------------------------------------
def restart(s, w_stary, nazwa):
    w_stary.przerwij("STOP")
    cb2 = CB(s)
    cb2.postac = PostacD(s)
    logi = []
    ops2 = OpsD(s)
    ops2.log = logi.append
    w2 = W.Wyprawa(cb2, ops2, konf=Konf(), log=logi.append, plik_stanu=w_stary.plik_stanu, plik_sklepow=W.PLIK_SKLEPOW,
                   plik_npc=TMP / f"npc_{nazwa}.json", plik_stop=TMP / f"STOP_{nazwa}", czas=lambda: s.wall)
    w2.logi = logi
    return cb2, w2


s = swiat(otworz_od=1)
cb, w = uruchom(s)
ruszaj(s, cb, w)
jedz(s, cb, w, fn=lambda i: w.faza == "sklep" and w.w and w.w["stops"][w.w["k"]]["id"] == "frodo")
poz_sklep = tuple(s.poz)
cb2, w2 = restart(s, w, "e1")
n, wyst, _ = jedz(s, cb2, w2)
kon = ev(s, "wyprawa_koniec")
sprawdz("7a restart przy Frodo (faza sklep, za drzwiami): wznowiona, zakupy, powrót przez drzwi, koniec ok",
        wyst and any("WZNOWIONA" in l and "sklep" in l for l in w2.logi) and s.plecak.get(3582, 0) >= 3
        and kon and kon[-1]["wynik"] in ("ok", "bez_zakupow") and s.poz[2] == 8 and s.uzyc == 1, (poz_sklep, w2.logi[:3], kon, s.plecak))

s = swiat(otworz_od=1)
cb, w = uruchom(s)
ruszaj(s, cb, w)
wnetrze = {tuple(p) for p in POW[2:6]}
jedz(s, cb, w, fn=lambda i: w.faza == "z" and tuple(s.poz) in wnetrze)
poz_pow = tuple(s.poz)
zamkn_przed = DRZWI in s.zamkniete
cb2, w2 = restart(s, w, "e2")
n, wyst, _ = jedz(s, cb2, w2)
kon = ev(s, "wyprawa_koniec")
sprawdz("7b restart w połowie powrotu (wnętrze chaty, przed drzwiami): wznowiona (faza z), wychodzi przez drzwi, koniec ok",
        wyst and any("WZNOWIONA" in l and "faza z" in l for l in w2.logi) and kon and kon[-1]["wynik"] in ("ok", "bez_zakupow")
        and s.poz[2] == 8 and not zamkn_przed and s.uzyc == 1, (poz_pow, w2.logi[:3], kon))
# 7c: restart po wyjściu na zewnątrz drzwi, z drzwiami zamkniętymi za nami (postać nie musi ich używać)
s = swiat(otworz_od=1)
cb, w = uruchom(s)
ruszaj(s, cb, w)
zewn = {tuple(p) for p in POW[7:]}
jedz(s, cb, w, fn=lambda i: w.faza == "z" and tuple(s.poz) in zewn)
cb2, w2 = restart(s, w, "e3")
n, wyst, _ = jedz(s, cb2, w2)
kon = ev(s, "wyprawa_koniec")
sprawdz("7c restart już za drzwiami (powrót): wznowiona, dochodzi do z8 bez użycia drzwi", wyst and kon and kon[-1]["wynik"] in ("ok", "bez_zakupow") and s.poz[2] == 8
        and s.uzyc == 1, (w2.logi[:3], s.uzyc, kon))

# 8. N3 (14.10): _dziura, łopata tylko na z7 (PIETRA_LOPATA_TYLKO_Z7); z8 + nieudany krok = brak łopaty
class _OpsL:
    def __init__(o):
        o.lopaty = []
    def uzyj_lopate(o, cel, poz):
        o.lopaty.append(tuple(cel))
    def uzyj_pole(o, pole, poz):
        pass

def _proba_dziury(z, tylko_z7=1, lopata=1):
    s = swiat(poz=(32493, 32258, z))
    cb, w = uruchom(s, maks=1)
    w.ops = _OpsL()
    k = w.konf
    k.PIETRA_LOPATA_TYLKO_Z7 = tylko_z7
    k.PIETRA_LOPATA = lopata
    w._po_przejsciu = lambda *a, **kw: False         # krok nie zmienia piętra (dziura zasypana)
    e = {"dziura": (32493, 32259, z), "stoi": (32493, 32258, z), "ladunek": (32493, 32259, z + 1),
         "pewna": True, "proby": 1}                  # n=1 -> tryb "lopata" w kolejności pewnej dziury
    w._dziura((32493, 32258, z), e, 1000.0)
    return w.ops.lopaty

sprawdz("8a z7 + nieudany krok: łopata użyta", len(_proba_dziury(7)) == 1)
sprawdz("8b z8 + nieudany krok: brak łopaty (TYLKO_Z7=1)", _proba_dziury(8) == [])
sprawdz("8c z8 + TYLKO_Z7=0: łopata (dawne zachowanie)", len(_proba_dziury(8, tylko_z7=0)) == 1)
sprawdz("8d z7 + PIETRA_LOPATA=0: brak łopaty", _proba_dziury(7, lopata=0) == [])

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
