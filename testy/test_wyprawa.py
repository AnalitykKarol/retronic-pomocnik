"""Wyprawa po zapasy (wyprawa.py) na atrapach: świat z NPC (Gorn, Frodo, Xodet), capem, złotem, głodem i piętrami
na prawdziwych plikach tras (troll_do_miasta / troll_z_miasta) i prawdziwej mapie. Nic nie trafia do gry
(RETRONIC_TESTY=1, brak XTEST, brak DISPLAY, brak gniazda)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import re
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot
import mapa as _mapa
import pokretla
import wypad
import wyprawa as W

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test wyprawy")
    sys.exit(0)
MAPA = _mapa.Mapa()
TMP = Path(tempfile.mkdtemp())
BAZA = W.punkty_bazy()
DO, Z, _ = BAZA["troll"]
GORN = DO[-1]
FRODO_NPC = (32369, 32241, 7)           # atrapa: pozycja Frodo (prawdziwa nieznana), pole przy temple Thais
XODET_NPC = (32361, 32232, 7)           # atrapa
START = DO[0]                            # z8, jaskinia trolli


class Konf:
    """Atrapa modułu cavebot: wartości pokręteł wyprawy (domyślne jak w cavebot.py)."""
    WYPAD_PO_TORCHE = True
    WYPAD_JEDZENIE = False
    WYPAD_ILE_TORCHY = 5
    WYPAD_ZAKUPY = {"torch": 5}
    WYPAD_SPRAWDZ_S = 15.0
    WYPAD_JEDZENIE_HP = 50.0
    WYPAD_JEDZENIE_SPOKOJ_S = 10.0
    JEDZENIE_ZAPAS_MIN = 5
    JEDZENIE_CZAR_AKTYWNY = 0
    WYPRAWA_AKTYWNA = 1
    WYPRAWA_ZAPAS_PROG = 0
    WYPRAWA_JEDZENIE_CEL = 20
    WYPRAWA_JEDZENIE_DOKUP = 5
    WYPRAWA_JEDZ_NA_MIEJSCU = 1
    WYPRAWA_JEDZ_MAKS = 12
    WYPRAWA_BLANKI = 0
    WYPRAWA_BLANKI_PROG = 2
    WYPRAWA_BLANKI_MAX_KOSZT = 500
    WYPRAWA_POCHODNIE = 1
    WYPRAWA_CAP_REZERWA = 8
    WYPRAWA_ZLOTO_MIN = 30
    WYPRAWA_MIN_HP = 70
    WYPRAWA_CO_MIN = 20
    WYPRAWA_MAX_CZAS_S = 1800
    WYPRAWA_MAX_KROKOW = 6000
    WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CZEKAJ_NA_GLOD = 0
    WYPRAWA_WZNOW_WALIDUJ = 1
    WYPRAWA_TYLKO_DEPO = 0
    UH_STAN_PLIK = None


def przejscia(punkty):
    """Zmiany pięter w liście punktów -> {pole do wejścia (use/krok): lądowanie}."""
    wej = {}
    for a, b in zip(punkty, punkty[1:]):
        if a[2] != b[2]:
            if b[2] < a[2]:
                wej[("lina", (b[0], b[1] - 1, a[2]))] = tuple(b)
            else:
                wej[("dziura", (b[0], b[1], a[2]))] = tuple(b)
    return wej


class Swiat:
    """Gracz, plecak (id -> sztuk), cap, głód, NPC. Czas w s (zegar cb)."""

    def __init__(s, poz=START, jedzenie=2, zloto=500, cap=79.0, torch=5, hp=100):
        s.poz = list(poz)
        s.t = 1000.0
        s.wall = 5_000_000.0
        s.hp = hp
        s.cap = cap
        s.max_cap = 400.0
        s.plecak = {3003: 1}
        if jedzenie:
            s.plecak[3582] = jedzenie
            s.cap -= 13.6 * jedzenie
        if zloto:
            s.plecak[3031] = zloto
        if torch:
            s.plecak[2920] = torch
        s.syt = 0                      # ile zjedzono od ostatniego "głodu"; pełny przy >= SYT_MAX
        s.SYT_MAX = 4
        s.msgs, s.mowa, s.poz_log = [], [], []
        s.stwory = []
        s.cel = None
        s.ucieczka = False
        s.wej = {}
        s.wej.update(przejscia(DO))
        s.wej.update(przejscia(Z))
        s.pietra = [poz[2]]
        s.zdarzenia = []
        s.npc = {  # nazwa -> (pozycja, {produkt: (id, cena, waga)})
            "Gorn": (GORN, {"torch": (2920, 2, 5.0)}),
            "Frodo": (FRODO_NPC, {"ham": (3582, 8, 13.6), "meat": (3577, 5, 13.0), "cheese": (3607, 5, 5.0)}),
            "Xodet": (XODET_NPC, {"blank rune": (3147, 10, 1.2)}),
        }
        s.rozmowa = None               # (npc, produkt, n)
        s.oczek = None
        s.milczy = set()
        s.zajety = {}                  # npc -> ile razy odpowiedzieć "zajęty" na hi
        s.waga_serwera = {}            # produkt -> rzeczywista waga (inna niż zakładana)
        s.blokada_marszu = False
        s.alarmy = []
        s.zjedzone_tyle = 0

    # --- sieć/cap ---
    def gracz(s):
        return {"hp": s.hp, "max_hp": 100, "proc": float(s.hp), "cap": s.cap, "max_cap": s.max_cap,
                "mana": 50, "max_mana": 95}

    def ile_zlota(s):
        return s.plecak.get(3031, 0)

    # --- czat / NPC ---
    def blisko(s, npc):
        p, _ = s.npc[npc]
        return s.poz[2] == p[2] and max(abs(s.poz[0] - p[0]), abs(s.poz[1] - p[1])) <= 3

    def npc_say(s, npc, t):
        s.msgs.append({"autor": npc, "tekst": t, "kanal": "Default", "czas": "", "nr": None})

    def sys_say(s, t):
        s.msgs.append({"autor": "", "tekst": t, "kanal": "Default", "czas": "", "nr": None})

    def czat(s, t):
        s.mowa.append(t)
        s.msgs.append({"autor": "Ja", "tekst": t, "kanal": "Default", "czas": "", "nr": None})
        l = t.lower().strip()
        npc = next((n for n in s.npc if s.blisko(n) and n not in s.milczy), None)
        if npc is None:
            return
        katalog = s.npc[npc][1]
        m = re.match(r"buy (\d+) (.+)$", l)
        if l == "hi":
            if s.zajety.get(npc, 0) > 0:
                s.zajety[npc] -= 1
                s.npc_say(npc, "Sorry, I am talking to Bob right now. Please wait a moment.")
                return
            s.rozmowa = npc
            s.npc_say(npc, f"Hello, hello, Ja! Please come in, look, and buy!")
        elif m and s.rozmowa == npc:
            n, nazwa = int(m[1]), m[2].strip()
            nazwa = nazwa[:-1] if nazwa.endswith("s") and nazwa[:-1] in katalog else nazwa
            if nazwa not in katalog:
                s.npc_say(npc, "Sorry, I do not sell that.")
                return
            ident, cena, waga = katalog[nazwa]
            waga = s.waga_serwera.get(nazwa, waga)
            if s.ile_zlota() < n * cena:
                s.npc_say(npc, "You do not have enough gold.")
            elif s.cap < n * waga:
                s.npc_say(npc, "You do not have enough capacity.")
            else:
                s.oczek = (npc, nazwa, n)
                s.npc_say(npc, f"Do you want to buy {n} {nazwa}s for {n * cena} gold coins?")
        elif l == "yes" and s.oczek:
            npc2, nazwa, n = s.oczek
            s.oczek = None
            ident, cena, waga = s.npc[npc2][1][nazwa]
            waga = s.waga_serwera.get(nazwa, waga)
            s.plecak[3031] = s.ile_zlota() - n * cena
            s.plecak[ident] = s.plecak.get(ident, 0) + n
            s.cap -= n * waga
            s.cap += n * cena * 0.1            # monety ważą 0,1 oz
            s.npc_say(npc2, "Thank you.")
        elif l == "no" and s.oczek:
            s.oczek = None
            s.npc_say(npc, "Then not.")

    # --- jedzenie ---
    def zjedz(s):
        for ident in (3582, 3577, 3607):
            if s.plecak.get(ident, 0) > 0:
                if s.syt >= s.SYT_MAX:
                    s.sys_say("You are full.")
                    return []
                s.plecak[ident] -= 1
                s.cap += {3582: 13.6, 3577: 13.0, 3607: 5.0}[ident]
                s.syt += 1
                s.zjedzone_tyle += 1
                return ["ham"]
        return []


class Postac:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def krok(p, k):
        s = p.s
        d = bot.KIERUNKI[k]
        n = (s.poz[0] + d[0], s.poz[1] + d[1], s.poz[2])
        w = s.wej.get(("dziura", n))
        s.t += 0.2
        if w:
            s.poz[:] = list(w)
        else:
            s.poz[:] = list(n)
        s.pietra.append(s.poz[2]) if s.pietra[-1] != s.poz[2] else None
        return tuple(s.poz)

    def klawisz(p, k):
        pass


class CB:
    """Cavebot w pigułce: tylko to, czego używa Wypad/Wyprawa."""

    def __init__(c, s, mapa=MAPA):
        c.s = s
        c.mapa = mapa
        c.postac = Postac(s)
        c.cel = None
        c.ucieczka = False
        c.ostrozny = False
        c.w_poscigu = False
        c.pamiec = None
        c.w_lootcie = False
        c.lww = None
        c.lww_zalegle = None
        c.zwloki_czekajace = []
        c.stan = "IDZ"
        c.ruch_poz = tuple(s.poz)
        c.ostatnie_stwory = []
        c.prog_aktualny = 30
        c.jedzenie_plecak = None
        c.jedzenie_nie_do = float("-inf")
        c.wypad_aktywny = False
        c.wypad_czat = None
        c.sciany = set()
        c.zablokowane = set()
        c.potwory = None
        c.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: s.zdarzenia.append((typ, d)))
        c.alarm = lambda t: s.alarmy.append(t)
        c.wroty = []
        c.uh_restore = False

    def zegar(c):
        return c.s.t

    def spij(c, d):
        c.s.t += d

    def pauza(c, a=0.1, b=0.3):
        c.s.t += (a + b) / 2

    def gracz(c):
        return c.s.gracz()

    def ustaw_stan(c, a, b=""):
        c.stan = a

    def _wypad_reset_klik(c):
        pass

    def _zywe_w_promieniu(c, lista, poz, odl):
        return [m for m in lista or [] if not m.get("gracz") and m.get("z") == poz[2] and m.get("hp", 100) > 0
                and max(abs(m["x"] - poz[0]), abs(m["y"] - poz[1])) <= odl]

    def droga(c, od, do, dlugosc=0):
        return []

    def krok_do(c, cel):
        c.s.t += 0.3

    def _idz_odcinek(c, punkty, idx):
        s = c.s
        s.t += 0.6
        if s.blokada_marszu:
            return False, idx
        idx = min(idx + 1, len(punkty) - 1)
        p = punkty[idx]
        if p[2] == s.poz[2]:
            s.poz[:] = list(p)
        return True, idx

    def _wypad_wroc_na_trase(c, poz):
        c.wroty.append(tuple(poz))
        return True

    def jedzenie_znane_brak(c, teraz):
        return teraz < c.jedzenie_nie_do

    def _czar_blokada(c):
        return None


class Ops:
    id_przedmiotow = {"torch": {2920}, "ham": {3582}, "blank": {3147}}
    id_jedzenia = {3582, 3577, 3607}

    def __init__(o, s):
        o.s = s
        o.zjedz_wyjatek = False

    def ekwipunek(o):
        return {10: 2925}

    def plecak(o):
        return {"id": {k: v for k, v in o.s.plecak.items() if v > 0}}

    def wiadomosci(o):
        w, o.s.msgs[:] = list(o.s.msgs), []
        return w

    def czat(o, t):
        o.s.czat(t)

    def uzyj_pole(o, pole, poz):
        s = o.s
        s.t += 0.5
        w = s.wej.get(("lina", tuple(pole))) or s.wej.get(("dziura", tuple(pole)))
        if w and max(abs(s.poz[0] - pole[0]), abs(s.poz[1] - pole[1])) <= 1 and s.poz[2] == pole[2]:
            s.poz[:] = list(w)
            if s.pietra[-1] != s.poz[2]:
                s.pietra.append(s.poz[2])

    def uzyj_line(o, cel, poz):
        o.uzyj_pole(cel, poz)

    def zjedz(o):
        if o.zjedz_wyjatek:
            raise RuntimeError("zrzut nie działa")
        o.s.t += 0.8
        return o.s.zjedz()


def konfig_sklepow(frodo=FRODO_NPC, xodet=XODET_NPC, nazwa="sklepy.json"):
    p = TMP / nazwa
    p.write_text(json.dumps({"przystanki": {
        "frodo": {"npc": "Frodo", "npc_poz": list(frodo) if frodo else None, "stoi": None},
        "xodet": {"npc": "Xodet", "npc_poz": list(xodet) if xodet else None, "stoi": None,
                  "slowa": {"blank": "blank rune"}}}}))
    return p


_n = [0]


def nowy(poz=START, konf=None, sklepy=None, npc_plik=None, stan=None, swiat=None, **kw):
    _n[0] += 1
    s = swiat or Swiat(poz=poz, **kw)
    cb = CB(s)
    k = konf or Konf()
    logi = []
    ops = Ops(s)
    ops.log = logi.append
    w = W.Wyprawa(cb, ops, konf=k, log=logi.append, plik_stanu=stan or (TMP / f"stan{_n[0]}.json"),
                  plik_sklepow=sklepy or konfig_sklepow(), plik_npc=npc_plik or (TMP / f"npc{_n[0]}.json"),
                  plik_stop=TMP / f"STOP{_n[0]}", czas=lambda: s.wall)
    w.logi = logi
    return s, cb, w, k


def ev(s, typ):
    return [d for t, d in s.zdarzenia if t == typ]


def bieg(s, cb, w, maks=4000, fn=None, zatrzymaj_po_koncu=True):
    """Driver jak Cavebot.idz(): wypad ma pierwszeństwo, ale nie w walce. Zwraca (liczba ticków, czy wystartowało)."""
    start = False
    for i in range(maks):
        s.t += 0.3
        s.wall += 0.3
        cb.ruch_poz = tuple(s.poz)
        cb.ostatnie_stwory = list(s.stwory)
        cb.cel = s.cel
        cb.ucieczka = s.ucieczka
        if fn:
            fn(i)
        if cb.cel is not None and not w.aktywny:
            continue
        if cb.ucieczka and w.aktywny:
            w.uciekaj(tuple(s.poz))
            continue
        w.tick()
        if w.aktywny:
            start = True
        elif start and zatrzymaj_po_koncu:
            return i, True
    return maks, start


def pre(s, cb, w, n=4):
    """Kilka odczytów wyzwalacza (potwierdzenie): zwraca czy wyprawa wystartowała."""
    for _ in range(n):
        s.t += 20
        s.wall += 20
        cb.ruch_poz = tuple(s.poz)
        cb.ostatnie_stwory = list(s.stwory)
        cb.cel = s.cel
        if w._okazja(s.t):
            return True
    return False


# --- 0. dane i pokrętła ---------------------------------------------------------
sprawdz("0a trasa bazowa troll kończy się u Gorna z7, z_miasta zaczyna się tam", GORN == (32377, 32201, 7) and Z[0] == GORN)
klucze = [k for k in vars(Konf) if k.startswith("WYPRAWA_")]
sprawdz("0b wszystkie pokrętła WYPRAWA_* w pokretla.ZAKRESY", all(k in pokretla.ZAKRESY for k in klucze if k != "WYPRAWA_AKTYWNA") and "WYPRAWA_AKTYWNA" in pokretla.ZAKRESY,
        [k for k in klucze if k not in pokretla.ZAKRESY])
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
sprawdz("0c w cavebot.py są stałe WYPRAWA_*, WYPRAWA_AKTYWNA domyślnie 0",
        all(hasattr(cavebot, k) for k in klucze) and cavebot.WYPRAWA_AKTYWNA == 0,
        [k for k in klucze if not hasattr(cavebot, k)])
tryby = json.loads((Path(W.KATALOG) / "tryby.json").read_text())
okt, blt = pokretla.waliduj(tryby["wyprawa"]["pokretla"])
sprawdz("0d tryb 'wyprawa' w tryby.json jest poprawny i włącza WYPRAWA_AKTYWNA", not blt and okt.get("WYPRAWA_AKTYWNA") == 1, blt)
okd, bld = pokretla.waliduj(tryby["wyprawa_depo"]["pokretla"])
sprawdz("0d2 tryb 'wyprawa_depo' poprawny: AKTYWNA, CZEKAJ_NA_GLOD i TYLKO_DEPO = 1",
        not bld and okd.get("WYPRAWA_AKTYWNA") == 1 and okd.get("WYPRAWA_TYLKO_DEPO") == 1
        and okd.get("WYPRAWA_CZEKAJ_NA_GLOD") == 1, bld)
okb, blb = pokretla.waliduj(tryby["wyprawa_blanki"]["pokretla"])
sprawdz("0e tryb 'wyprawa_blanki' poprawny", not blb and okb.get("WYPRAWA_BLANKI") == 30, blb)
ok_, bl_ = pokretla.waliduj({"WYPRAWA_AKTYWNA": 1, "WYPRAWA_CO_MIN": 5}, {"WYPRAWA_AKTYWNA": 0, "WYPRAWA_CO_MIN": 20})
sprawdz("0f analityk nie włączy wyprawy ani nie skróci odstępu", not ok_ and len(bl_) == 2, f"{ok_} {bl_}")
sprawdz("0g aktywna wyprawa zastępuje wyzwalacz jedzenia wypadu (Al Dee)",
        (lambda: W.Wyprawa(CB(Swiat()), Ops(Swiat()), konf=Konf(), plik_stanu=TMP / "x.json")._k("WYPAD_JEDZENIE", True) is False)())

# --- 1. wyzwalacz ----------------------------------------------------------------
s, cb, w, k = nowy(jedzenie=2)
sprawdz("1a zapas 2 < 5: start po 2 odczytach, powód zapas", pre(s, cb, w) and w.powod.startswith("wyprawa:zapas") and cb.wypad_aktywny, w.powod)
s, cb, w, k = nowy(jedzenie=2)
sprawdz("1b pierwszy odczyt nie startuje (debounce)", not pre(s, cb, w, 1) and not cb.wypad_aktywny)
s, cb, w, k = nowy(jedzenie=6)
sprawdz("1c zapas 6 >= 5: brak startu", not pre(s, cb, w, 5))
s, cb, w, k = nowy(jedzenie=0)
cb.jedzenie_nie_do = s.t + 1000
sprawdz("1d brak jedzenia (głód): start", pre(s, cb, w) and "zapas" in w.powod or "glod" in w.powod, w.powod)
# 1d2. WYPRAWA_CZEKAJ_NA_GLOD: start dopiero po potwierdzonym głodzie
def konf_glod(v=1):
    kk = Konf(); kk.WYPRAWA_CZEKAJ_NA_GLOD = v
    return kk
s, cb, w, k = nowy(jedzenie=0, konf=konf_glod())
sprawdz("1d2 CZEKAJ_NA_GLOD=1, najedzony + zapas 0: nie rusza", not pre(s, cb, w, 6) and not cb.wypad_aktywny)
s, cb, w, k = nowy(jedzenie=2, konf=konf_glod())
sprawdz("1d3 CZEKAJ_NA_GLOD=1, najedzony + zapas 2 < prog: nie rusza", not pre(s, cb, w, 6))
s, cb, w, k = nowy(jedzenie=0, konf=konf_glod())
cb.jedzenie_nie_do = s.t + 1000
sprawdz("1d4 CZEKAJ_NA_GLOD=1, po nieudanej próbie jedzenia: rusza (glod/zapas)",
        pre(s, cb, w) and ("zapas" in w.powod or "glod" in w.powod), w.powod)
s, cb, w, k = nowy(jedzenie=0, konf=konf_glod())
cb.jedzenie_nie_do = s.t + 100
pre(s, cb, w, 1)                      # 1 odczyt: potwierdzony głód zapamiętany
cb.jedzenie_nie_do = float("-inf")    # okno cavebota minęło, pamięć wyprawy trzyma
s.t += 200
sprawdz("1d5 CZEKAJ_NA_GLOD=1, głód zapamiętany po wygaśnięciu okna cavebota: rusza", pre(s, cb, w, 3) and cb.wypad_aktywny, w.powod)
s, cb, w, k = nowy(jedzenie=0, konf=konf_glod())
cb.jedzenie_nie_do = s.t + 100
pre(s, cb, w, 1)
cb.jedzenie_nie_do = float("-inf")
s.t += 5000
sprawdz("1d6 CZEKAJ_NA_GLOD=1, stary głód (> 10 min): nie rusza", not pre(s, cb, w, 4))
s, cb, w, k = nowy(jedzenie=0, konf=konf_glod(0))
sprawdz("1d7 CZEKAJ_NA_GLOD=0: dawne zachowanie, zapas 0 rusza od razu", pre(s, cb, w) and cb.wypad_aktywny, w.powod)
kj = konf_glod(0); kj.WYPRAWA_JEDZENIE = 0
s, cb, w, k = nowy(jedzenie=0, konf=kj)
cb.jedzenie_nie_do = s.t + 100
sprawdz("1d7b WYPRAWA_JEDZENIE=0: zapas 0 i głód nie ruszają wyprawy", not pre(s, cb, w, 6) and not cb.wypad_aktywny)
okg, blg = pokretla.waliduj({"WYPRAWA_CZEKAJ_NA_GLOD": 1}, {"WYPRAWA_CZEKAJ_NA_GLOD": 0})
sprawdz("1d8 analityk nie podniesie CZEKAJ_NA_GLOD (nie_wyzej), zakres 0/1", not okg and len(blg) == 1, f"{okg} {blg}")
k = Konf(); k.WYPRAWA_AKTYWNA = 0
s, cb, w, k = nowy(jedzenie=0, konf=k)
sprawdz("1e WYPRAWA_AKTYWNA=0 (domyślnie): brak startu", not pre(s, cb, w, 5))
for opis, kw, mod in (("walka (cel)", {}, lambda s, cb, w: setattr(s, "cel", {"id": 1})),
                      ("HP 50%", {"hp": 50}, None),
                      ("mob w promieniu 8", {}, lambda s, cb, w: s.stwory.append({"id": 5, "nazwa": "Troll", "gracz": False, "x": s.poz[0] + 3, "y": s.poz[1], "z": s.poz[2], "hp": 100})),
                      ("obcy gracz w widoku", {}, lambda s, cb, w: s.stwory.append({"id": 6, "nazwa": "Rycerz", "gracz": True, "x": s.poz[0] + 5, "y": s.poz[1], "z": s.poz[2], "hp": 100})),
                      ("za mało złota (10 < 30)", {"zloto": 10}, None),
                      ("brak capa (10 oz)", {"cap": 10.0}, None),
                      ("zwłoki czekają na loot", {}, lambda s, cb, w: cb.zwloki_czekajace.append(((1, 1, 8), 0))),
                      ("UH w toku (zdjęta tarcza)", {}, lambda s, cb, w: setattr(cb, "uh_restore", True)),
                      ("trwa ucieczka", {}, lambda s, cb, w: setattr(s, "ucieczka", True))):
    s, cb, w, k = nowy(jedzenie=1, **kw)
    if mod:
        mod(s, cb, w)
    cb.ucieczka = s.ucieczka
    wyn = False
    for _ in range(5):
        s.t += 20
        s.wall += 20
        cb.ruch_poz, cb.ostatnie_stwory, cb.cel = tuple(s.poz), list(s.stwory), s.cel
        cb.ucieczka = s.ucieczka
        wyn = wyn or w._okazja_wyprawa(s.t)
    sprawdz(f"1f brak startu: {opis}", not wyn and not cb.wypad_aktywny)
# cooldown po poprzedniej wyprawie (zegar ścienny w pliku stanu)
s, cb, w, k = nowy(jedzenie=1)
w._stan_zapisz(nast_wall=s.wall + 600)
sprawdz("1g cooldown WYPRAWA_CO_MIN (nast_wall w pliku): brak startu", not pre(s, cb, w, 5))
# UH_STAN_PLIK z zapamiętaną tarczą
uhp = TMP / "uh_stan.json"
uhp.write_text(json.dumps({"tarcza_id": 3426}))
k = Konf(); k.UH_STAN_PLIK = uhp
s, cb, w, k = nowy(jedzenie=1, konf=k)
sprawdz("1h UH_STAN_PLIK z tarcza_id (tarcza zdjęta): brak startu", not pre(s, cb, w, 5))
# nieznana pozycja Frodo
s, cb, w, k = nowy(jedzenie=1, sklepy=konfig_sklepow(frodo=None, nazwa="bez_frodo.json"))
sprawdz("1i nieznana pozycja Frodo: nie startuje, jest wpis i cooldown 30 min",
        not pre(s, cb, w, 5) and not cb.wypad_aktywny and w.nast_wyprawa > s.t, w.logi[-2:])
# uczenie pozycji NPC z widoku
s, cb, w, k = nowy(jedzenie=1, sklepy=konfig_sklepow(frodo=None, nazwa="bez_frodo2.json"))
cb.ostatnie_stwory = [{"id": 9, "nazwa": "Frodo", "gracz": False, "x": 32369, "y": 32241, "z": 7, "hp": 100}]
w._ucz_npc(cb.ostatnie_stwory, 0.0)
sprawdz("1j Frodo widziany w liście stworów: pozycja zapisana do wyprawa_npc.json",
        w.npc_widziane.get("Frodo") == (32369, 32241, 7) and json.loads(w.plik_npc.read_text())["Frodo"]["poz"] == [32369, 32241, 7])
s, cb, w, k = nowy(jedzenie=1, sklepy=konfig_sklepow(frodo=None, nazwa="bez_frodo3.json"), npc_plik=w.plik_npc)
sprawdz("1k po restarcie pozycja Frodo wczytana i wyprawa startuje", pre(s, cb, w, 4) and cb.wypad_aktywny)

# --- 2. pełna wyprawa: Gorn (pochodnie) -> Frodo (kup, jedz do full, dokup) -> powrót ----------------
s, cb, w, k = nowy(jedzenie=2, torch=1)
n, wyst = bieg(s, cb, w, maks=9000, fn=None) if pre(s, cb, w) else (0, False)
kon = ev(s, "wyprawa_koniec") or ev(s, "wypad_koniec")
sprawdz("2a wyprawa wykonana: start, koniec ok, stan SPOKOJ", wyst and not cb.wypad_aktywny and w.stan == "SPOKOJ"
        and kon and kon[-1]["wynik"] == "ok", f"n={n} kon={kon} log={w.logi[-4:]}")
sprawdz("2b dialog: hi / buy torch / yes u Gorna, potem hi / buy ham / yes u Frodo (bez nicków)",
        s.mowa[:3] == ["hi", "buy 4 torch", "yes"] and "buy 5 ham" in s.mowa or "buy 4 ham" in s.mowa or any(x.startswith("buy ") and x.endswith(" ham") for x in s.mowa),
        s.mowa)
sprawdz("2c pochodnie dokupione do 5", s.plecak.get(2920) == 5, s.plecak)
sprawdz("2d zjedzono u NPC do 'full' (SYT_MAX=4) i dokupiono jedzenie", s.zjedzone_tyle >= 3 and s.plecak.get(3582, 0) >= 3, (s.zjedzone_tyle, s.plecak))
DBGLOG = w.logi[-25:]
sprawdz("2e cap nigdy poniżej rezerwy po zakupach (>= 8 oz) i nie ujemny", s.cap >= 8 - 1e-6, s.cap)
sprawdz("2f złoto nie ujemne, wydane tylko na zakupy", s.ile_zlota() >= 0 and s.ile_zlota() < 500, s.ile_zlota())
sprawdz("2g piętra: z8 -> z9 -> z8 -> z7 (miasto) -> z7... -> powrót z7 -> z8", s.pietra[0] == 8 and 7 in s.pietra and s.pietra[-1] == 8, s.pietra)
sprawdz("2h koniec: wypad_wroc_na_trase wywołane, flaga wypadu zdjęta, stan zapisany jako nieaktywny",
        cb.wroty and not cb.wypad_aktywny and json.loads(w.plik_stanu.read_text()).get("aktywna") is False
        and json.loads(w.plik_stanu.read_text()).get("nast_wall", 0) > s.wall, cb.wroty)
st = json.loads(w.plik_stanu.read_text())
sprawdz("2i waga ham poprawiona z delty cap (13.6) i cena zapisana (8 gp)", abs(st["wagi"].get("ham", 0) - 13.6) < 0.5 and abs(st["ceny"].get("ham", 0) - 8) < 0.01, st.get("wagi"))
sprawdz("2j po wyprawie brak ponownego startu (cooldown), zapas 6+ i tak powyżej progu", not pre(s, cb, w, 4))
sprawdz("2k telemetria: wyprawa_koniec z kupionymi, są kroki jedzenia", ev(s, "wyprawa_koniec") and any(d.get("rodzaj") == "jedzenie_koniec" for d in ev(s, "wyprawa_krok")),
        [t for t, _ in s.zdarzenia][:20])

# --- 3. złoto ----------------------------------------------------------------------
s, cb, w, k = nowy(jedzenie=1, zloto=50, torch=5)
n, wyst = bieg(s, cb, w, maks=9000) if pre(s, cb, w) else (0, False)
sprawdz("3a mało złota (50 gp, ham 8): oferta ponad budżet obcięta z góry do mieszczącej się, złoto >= 0",
        wyst and s.ile_zlota() >= 0 and s.plecak.get(3582, 0) >= 3 and ev(s, "wyprawa_koniec")[-1]["wynik"] == "ok",
        (s.mowa, s.plecak))
s, cb, w, k = nowy(jedzenie=1, zloto=35, torch=5, cap=120.0)   # P5 13.10: domyślna waga ham 20 oz (dane), cap nie ma ograniczać
n, wyst = bieg(s, cb, w, maks=9000) if pre(s, cb, w) else (0, False)
sprawdz("3b złoto 35: kupione tyle ile starcza (4 szt. = 32 gp), bez pętli próśb", "buy 4 ham" in s.mowa and s.ile_zlota() >= 0 and s.mowa.count("hi") <= 3, (s.plecak, s.mowa))

# --- 4. capacity -------------------------------------------------------------------
s, cb, w, k = nowy(jedzenie=0, cap=40.0, zloto=500, torch=5)
cb.jedzenie_nie_do = s.t + 10 ** 6
n, wyst = bieg(s, cb, w, maks=9000) if pre(s, cb, w) else (0, False)
sprawdz("4a cap 40 oz: zakup obcięty do (40-8)/13.6 = 2 szt., cap >= rezerwa, wyprawa ok",
        wyst and s.cap >= 8 - 1e-6 and s.plecak.get(3582, 0) >= 2, (s.cap, s.plecak, s.mowa))
# serwer ma inną wagę niż zakładamy (25 oz): odrzuca "capacity", bot zmniejsza o połowę i kupuje
s, cb, w, k = nowy(jedzenie=0, cap=79.0, zloto=500, torch=5)
s.waga_serwera["ham"] = 25.0
cb.jedzenie_nie_do = s.t + 10 ** 6
n, wyst = bieg(s, cb, w, maks=9000) if pre(s, cb, w) else (0, False)
sprawdz("4b serwer odrzuca za duży zakup (capacity): ponowienie z połową, ostatecznie kupione, bez pętli",
        wyst and s.plecak.get(3582, 0) >= 1 and any("cap" in l.lower() or "miejsc" in l.lower() for l in w.logi) and len([x for x in s.mowa if x.startswith("buy")]) <= 8,
        (s.plecak, s.mowa))
# jedzenie przed zakupem: pełny plecak (cap 10 po starcie) - start zablokowany przed marszem
s, cb, w, k = nowy(jedzenie=0, cap=12.0, zloto=500)
sprawdz("4c brak capa na choćby 1 szt. + rezerwa: wyprawa się nie zaczyna (bez marszu na darmo)", not pre(s, cb, w, 5) and not cb.wypad_aktywny)

# --- 5. blanki (Xodet) -----------------------------------------------------------------
k5 = Konf(); k5.WYPRAWA_BLANKI = 10; k5.WYPRAWA_BLANKI_MAX_KOSZT = 50
s, cb, w, k = nowy(jedzenie=1, torch=5, konf=k5)
n, wyst = bieg(s, cb, w, maks=12000) if pre(s, cb, w) else (0, False)
sprawdz("5a blanki: kupione u Xodeta do limitu kosztu (50 gp / 10 gp = 5 szt.), jedzenie u Frodo też",
        wyst and s.plecak.get(3147, 0) == 5 and s.plecak.get(3582, 0) >= 3 and any(x == "buy 10 blank rune" or x.startswith("buy ") and "blank" in x for x in s.mowa),
        (s.plecak, s.mowa))
k5 = Konf(); k5.WYPRAWA_BLANKI = 10
s, cb, w, k = nowy(jedzenie=1, torch=5, konf=k5, sklepy=konfig_sklepow(xodet=None, nazwa="bez_xodet.json"))
n, wyst = bieg(s, cb, w, maks=12000) if pre(s, cb, w) else (0, False)
sprawdz("5b nieznana pozycja Xodeta: przystanek pominięty (log), jedzenie kupione, wyprawa ok",
        wyst and s.plecak.get(3147, 0) == 0 and s.plecak.get(3582, 0) >= 3 and ev(s, "wyprawa_koniec")[-1]["wynik"] == "ok"
        and any("pomijam przystanek xodet" in l for l in w.logi), w.logi[-5:])
k5 = Konf(); k5.WYPRAWA_BLANKI = 0
s, cb, w, k = nowy(jedzenie=1, torch=5, konf=k5)
n, wyst = bieg(s, cb, w, maks=12000) if pre(s, cb, w) else (0, False)
sprawdz("5c WYPRAWA_BLANKI=0 (domyślnie): nie podchodzi do Xodeta, nie kupuje blanków", s.plecak.get(3147, 0) == 0 and not any("blank" in x for x in s.mowa))
# trigger z samych blanków
k5 = Konf(); k5.WYPRAWA_BLANKI = 10
s, cb, w, k = nowy(jedzenie=8, torch=5, konf=k5)
sprawdz("5d mało blanków (0 < próg 2) przy WYPRAWA_BLANKI>0: start z powodu blanki", pre(s, cb, w) and "blanki" in w.powod, w.powod)

# --- 6. NPC: zajęty / milczy ----------------------------------------------------------
s, cb, w, k = nowy(jedzenie=1, torch=5)
s.zajety["Frodo"] = 3
n, wyst = bieg(s, cb, w, maks=12000) if pre(s, cb, w) else (0, False)
sprawdz("6a Frodo zajęty (3x 'talking to Bob'): czekamy, nie liczy się jako porażka, zakup się udaje",
        wyst and s.plecak.get(3582, 0) >= 3 and ev(s, "wyprawa_kolejka") and ev(s, "wyprawa_koniec")[-1]["wynik"] == "ok"
        and w.porazki == 0, (s.mowa, w.logi[-6:]))
s, cb, w, k = nowy(jedzenie=1, torch=5)
s.milczy.add("Frodo")
powiad = []
import powiadom as _pw
_stare = _pw.powiadom
_pw.powiadom = lambda *a, **kw: powiad.append(a)
try:
    n, wyst = bieg(s, cb, w, maks=12000) if pre(s, cb, w) else (0, False)
finally:
    _pw.powiadom = _stare
kon = ev(s, "wyprawa_koniec")
sprawdz("6b Frodo milczy: 3x hi, brak_npc, powrót na spot, porażka + powiadomienie, blokada kolejnej próby",
        wyst and s.mowa.count("hi") == 3 and kon and kon[-1]["wynik"] != "ok" and s.poz[2] == 8 and s.plecak.get(3582, 0) == 1
        and w.porazki == 1 and w.blokada_do > s.t and powiad, (s.mowa, kon))

# --- 7. walka i ucieczka po drodze -------------------------------------------------------
s, cb, w, k = nowy(jedzenie=1, torch=5)
stan7 = {"walka": 0, "uciekl": 0}
def fn7(i):
    if w.aktywny and s.poz[2] == 9 and stan7["walka"] < 25:
        s.cel = {"id": 77}; stan7["walka"] += 1      # mob atakuje w jaskini: cavebot walczy, wypad czeka
    else:
        s.cel = None
    if w.aktywny and s.poz[2] == 7 and 5 < stan7["uciekl"] < 30:
        s.ucieczka = True
    else:
        s.ucieczka = False
    if w.aktywny and s.poz[2] == 7:
        stan7["uciekl"] += 1
n, wyst = bieg(s, cb, w, maks=12000, fn=fn7) if pre(s, cb, w) else (0, False)
sprawdz("7a mob po drodze (walka na z9) i ucieczka w mieście: wyprawa dokończona, kupione, powrót na z8",
        wyst and stan7["walka"] >= 5 and stan7["uciekl"] > 30 and s.plecak.get(3582, 0) >= 3 and s.poz[2] == 8
        and ev(s, "wyprawa_koniec")[-1]["wynik"] == "ok", (stan7, s.plecak, s.poz))

# --- 8. utknięcie ------------------------------------------------------------------------
s, cb, w, k = nowy(jedzenie=1, torch=5)
powiad = []
_pw.powiadom = lambda *a, **kw: powiad.append(a)
try:
    if pre(s, cb, w):
        s.blokada_marszu = True            # po starcie marsz nigdy nie rusza
        n, wyst = bieg(s, cb, w, maks=3000)
finally:
    _pw.powiadom = _stare
kon = ev(s, "wyprawa_koniec")
stop8 = TMP / f"STOP{_n[0]}"
sprawdz("8a utknięcie w marszu (zablokowana droga): koniec 'blad', alarm i zatrzymanie (plik STOP), powiadomienie",
        kon and kon[-1]["wynik"] == "blad" and s.alarmy and powiad and stop8.exists() and not cb.wypad_aktywny,
        (kon, s.alarmy, powiad, stop8.exists()))
# limit czasu
k8 = Konf(); k8.WYPRAWA_MAX_CZAS_S = 60
s, cb, w, k = nowy(jedzenie=1, torch=5, konf=k8)
_pw.powiadom = lambda *a, **kw: None
try:
    if pre(s, cb, w):
        bieg(s, cb, w, maks=5000)
finally:
    _pw.powiadom = _stare
kon = ev(s, "wyprawa_koniec")
sprawdz("8b twardy limit czasu (60 s): wyprawa przerwana i zakończona alarmem", kon and kon[-1]["wynik"] == "blad" and s.alarmy, kon)
# limit obiegów
k8 = Konf(); k8.WYPRAWA_MAX_KROKOW = 20
s, cb, w, k = nowy(jedzenie=1, torch=5, konf=k8)
_pw.powiadom = lambda *a, **kw: None
try:
    if pre(s, cb, w):
        bieg(s, cb, w, maks=8000)
finally:
    _pw.powiadom = _stare
sprawdz("8c limit obiegów (20) zadziałał (log limit_krokow), wyprawa nie wisi", any("limit_krokow" in str(d) for d in ev(s, "wypad_blad")) and not cb.wypad_aktywny, ev(s, "wypad_blad")[:2])

# --- 9. teleport / śmierć -----------------------------------------------------------------
s, cb, w, k = nowy(jedzenie=1, torch=5)
_pw.powiadom = lambda *a, **kw: None
try:
    def fn9(i):
        if w.aktywny and i > 5 and not getattr(fn9, "po", False):
            fn9.po = True
            s.poz[0] += 60                    # skok o dziesiątki pól na tym samym piętrze (śmierć/teleport)
    if pre(s, cb, w):
        bieg(s, cb, w, maks=3000, fn=fn9)
finally:
    _pw.powiadom = _stare
sprawdz("9 skok pozycji (śmierć/teleport): wyprawa przerwana, alarm + STOP, zablokowana", getattr(fn9, "po", False) and s.alarmy and w.zablokowany and not cb.wypad_aktywny,
        (s.alarmy, w.zablokowany))

# --- 10. STOP w środku i wznowienie po restarcie -----------------------------------------
s, cb, w, k = nowy(jedzenie=1, torch=5)
pre(s, cb, w)
stan_plik = w.plik_stanu
stare_stop, stare_env = bot.STOP, _os.environ.pop("RETRONIC_TESTY", None)
bot.STOP = TMP / "STOP10"            # nie zależymy od prawdziwego pliku STOP w katalogu bota
for i in range(3000):
    s.t += 0.3; s.wall += 0.3
    cb.ruch_poz = tuple(s.poz)
    w.tick()
    if s.poz[2] == 7 and len(s.pietra) > 3:
        break
poz_stop = tuple(s.poz)
(TMP / "STOP10").write_text("")
bot.STOP = TMP / "STOP10"
try:
    try:
        w.tick(); wyj = None
    except bot.Zatrzymano as e:
        wyj = e
finally:
    bot.STOP = stare_stop
    if stare_env is not None:
        _os.environ["RETRONIC_TESTY"] = stare_env
st = json.loads(stan_plik.read_text())
sprawdz("10a STOP w środku: Zatrzymano, wyprawa zablokowana, stan zapisany jako aktywny+przerwana",
        wyj is not None and w.zablokowany and st.get("aktywna") and st.get("przerwana") and st.get("k") is not None, st)
# "restart bota": nowa instancja, ta sama pozycja, ten sam plik stanu
s2 = s
cb2 = CB(s2)
logi2 = []
ops2 = Ops(s2); ops2.log = logi2.append
w2 = W.Wyprawa(cb2, ops2, konf=Konf(), log=logi2.append, plik_stanu=stan_plik, plik_sklepow=konfig_sklepow(),
               plik_npc=TMP / "npc_r.json", plik_stop=TMP / "STOP_r", czas=lambda: s2.wall)
start2 = False
for i in range(9000):
    s2.t += 0.3; s2.wall += 0.3
    cb2.ruch_poz = tuple(s2.poz); cb2.ostatnie_stwory = []
    w2.tick()
    if w2.aktywny:
        start2 = True
    elif start2:
        break
kon2 = [d for t, d in s2.zdarzenia if t in ("wyprawa_koniec",)]
sprawdz("10b restart w środku wyprawy: wznowiona od najbliższego odcinka (log WZNOWIONA), zakupy i powrót dokończone",
        start2 and any("WZNOWIONA" in l for l in logi2) and s2.plecak.get(3582, 0) >= 3 and s2.poz[2] == 8 and kon2 and kon2[-1]["wynik"] == "ok",
        (logi2[-4:], s2.plecak, s2.poz))
# restart tuż przy Frodo (faza sklep)
s3, cb3, w3, k3 = nowy(jedzenie=1, torch=5)
pre(s3, cb3, w3)
for i in range(6000):
    s3.t += 0.3; s3.wall += 0.3
    cb3.ruch_poz = tuple(s3.poz)
    w3.tick()
    if w3.faza == "sklep" and w3.w and w3.w["stops"][w3.w["k"]]["id"] == "frodo":
        break
w3.przerwij("STOP")
cb4 = CB(s3)
logi4 = []
ops4 = Ops(s3); ops4.log = logi4.append
w4 = W.Wyprawa(cb4, ops4, konf=Konf(), log=logi4.append, plik_stanu=w3.plik_stanu, plik_sklepow=konfig_sklepow(),
               plik_npc=TMP / "npc_r2.json", plik_stop=TMP / "STOP_r2", czas=lambda: s3.wall)
start4 = False
for i in range(9000):
    s3.t += 0.3; s3.wall += 0.3
    cb4.ruch_poz = tuple(s3.poz); cb4.ostatnie_stwory = []
    w4.tick()
    if w4.aktywny:
        start4 = True
    elif start4:
        break
sprawdz("10c restart przy Frodo (faza sklep): wznowiona, kupuje i je, wraca",
        start4 and any("WZNOWIONA" in l and "sklep" in l for l in logi4) and s3.plecak.get(3582, 0) >= 3 and s3.poz[2] == 8, (logi4[:3], s3.plecak))
# stary zapis i pozycja poza planem: bez wznowienia
st_stary = TMP / "stary.json"
st_stary.write_text(json.dumps({"aktywna": True, "baza": "troll", "k": 0, "t_wall": 1.0, "potrzeby": {"frodo": True}}))
s5, cb5, w5, k5 = nowy(jedzenie=9, stan=st_stary)
w5.tick()
sprawdz("10d stary zapis stanu (> 40 min): nie wznawia, stan wyczyszczony", not cb5.wypad_aktywny and json.loads(st_stary.read_text()).get("aktywna") is False)
st_poza = TMP / "poza.json"
st_poza.write_text(json.dumps({"aktywna": True, "baza": "troll", "k": 0, "t_wall": 5_000_000.0, "potrzeby": {"frodo": True}}))
_pw.powiadom = lambda *a, **kw: None
try:
    s6, cb6, w6, k6 = nowy(jedzenie=9, stan=st_poza, poz=(100, 100, 7))
    w6.tick()
finally:
    _pw.powiadom = _stare
sprawdz("10e pozycja poza planem: nie wznawia i nie rusza", not cb6.wypad_aktywny and json.loads(st_poza.read_text()).get("aktywna") is False)

# --- 11. zgodność: wypad po pochodnie bez wyprawy działa jak dawniej ------------------------
k11 = Konf(); k11.WYPRAWA_AKTYWNA = 0
s, cb, w, k = nowy(jedzenie=9, torch=0, konf=k11, cap=250.0)
class OpsT(Ops):
    def ekwipunek(o): return {10: 2926}       # wypalona pochodnia w slocie
s.t0 = 0
w.ops = OpsT(s)
w.ops.log = w.logi.append
wystartowal = pre(s, cb, w, 4)
sprawdz("11a WYPRAWA_AKTYWNA=0: torch-trip startuje jak w wypadzie (powód pochodnie)", wystartowal and w.powod == "pochodnie" and w.w is None, w.powod)
n, wyst = bieg(s, cb, w, maks=9000)
sprawdz("11b torch-trip dokończony: 5 pochodni u Gorna, bez jedzenia (domyślne zakupy)", wyst and s.plecak.get(2920) == 5 and s.mowa[:3] == ["hi", "buy 5 torch", "yes"], (s.mowa, s.plecak))

# --- 12. tryb wyprawa_depo: tylko do depo, STOP, bez zakupów ---------------------------------
DEPO = (32348, 32225, 7)   # początek trasy/depo_troll_cave.json (13.10: prawdziwe depo)
def konf_depo(**kw):
    kk = Konf(); kk.WYPRAWA_TYLKO_DEPO = 1; kk.WYPRAWA_CZEKAJ_NA_GLOD = 1
    for a, b in kw.items():
        setattr(kk, a, b)
    return kk
sp_bez = konfig_sklepow(frodo=None, xodet=None, nazwa="bez_npc.json")


def krok_dokladny(cb):
    """krok_do atrapy: gdy cel obok na tym samym piętrze, staje na nim (jak prawdziwy krok)."""
    def kd(cel, cb=cb):
        sw = cb.s
        sw.t += 0.3
        if len(cel) > 2 and cel[2] == sw.poz[2] and max(abs(sw.poz[0] - cel[0]), abs(sw.poz[1] - cel[1])) == 1:
            sw.poz[:] = [cel[0], cel[1], cel[2]]
    cb.krok_do = kd
    return cb


powiad12 = []
_pw.powiadom = lambda *a, **kw: powiad12.append(a)
try:
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez)
    krok_dokladny(cb)
    cb.jedzenie_nie_do = s.t + 100000
    stop12 = TMP / f"STOP{_n[0]}"
    plecak0 = dict(s.plecak)
    startuje = pre(s, cb, w)
    sprawdz("12a start bez pozycji Frodo, po potwierdzonym głodzie, powód depo", startuje and w.powod.startswith("wyprawa:depo")
            and w.w is not None and w.w["potrzeby"] == {"depo": True} and [st["id"] for st in w.w["stops"]] == ["depo"], (w.powod, w.w and w.w["potrzeby"]))
    n, wyst = bieg(s, cb, w, maks=12000)
    kon = ev(s, "wyprawa_koniec")
    stan = json.loads(w.plik_stanu.read_text())
    sprawdz("12b dojście do pola depo: koniec 'depo', STOP zapisany, stan wyczyszczony, wypad nieaktywny",
            wyst and tuple(s.poz) == DEPO and kon and kon[-1]["wynik"] == "depo" and stop12.exists()
            and stan.get("aktywna") is False and w.w is None and not cb.wypad_aktywny and w.zablokowany,
            (s.poz, kon, stop12.exists(), stan.get("aktywna")))
    sprawdz("12c bez zakupów i bez rozmowy z NPC, bez powrotu na spot, jedzenie bez zmian",
            s.mowa == [] and s.plecak == plecak0 and cb.wroty == [] and not ev(s, "wypad_zakup_odmowa") and w.kupione == {},
            (s.mowa, s.plecak, cb.wroty))
    sprawdz("12d powiadomienie o dotarciu do depo (critical) i brak alarmu utknięcia",
            any(a[0] == "Wyprawa: jestem w depo" and a[2] == "critical" for a in powiad12) and not s.alarmy, (powiad12, s.alarmy))
    sprawdz("12e nie wraca do jaskini: ostatnia pozycja z7, nigdy z8 po wyjściu z miasta",
            s.poz[2] == 7 and s.pietra[-1] == 7, s.pietra)
    # zwykła wyprawa z brakiem Frodo nadal nie startuje (kontrola zgodności)
    s, cb, w, k = nowy(jedzenie=0, konf=konf_glod(), sklepy=sp_bez)
    cb.jedzenie_nie_do = s.t + 100000
    sprawdz("12f TYLKO_DEPO=0 i brak Frodo: wyprawa po zakupy nie startuje jak dawniej", not pre(s, cb, w, 5) and not cb.wypad_aktywny)
    # bez głodu (zapas 0, najedzony): tryb depo nie rusza
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(WYPRAWA_CZEKAJ_NA_GLOD=0), sklepy=sp_bez)
    sprawdz("12g tryb depo zawsze czeka na potwierdzony głód (nawet gdy CZEKAJ_NA_GLOD=0)", not pre(s, cb, w, 6) and not cb.wypad_aktywny)
    # utknięcie w marszu: alarm + STOP, bez powrotu
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(WYPRAWA_STOP_PRZY_UTKNIECIU=0), sklepy=sp_bez)
    cb.jedzenie_nie_do = s.t + 100000
    stop12b = TMP / f"STOP{_n[0]}"
    if pre(s, cb, w):
        s.blokada_marszu = True
        bieg(s, cb, w, maks=3000)
    kon = ev(s, "wyprawa_koniec")
    sprawdz("12h utknięcie w marszu do depo: alarm + STOP (nawet przy STOP_PRZY_UTKNIECIU=0), wyprawa zakończona, bez powrotu",
            kon and kon[-1]["wynik"] == "blad" and s.alarmy and stop12b.exists() and not cb.wypad_aktywny and w.zablokowany
            and cb.wroty == [] and w.faza != "z", (kon, s.alarmy, stop12b.exists()))
    # limit czasu
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(WYPRAWA_MAX_CZAS_S=60), sklepy=sp_bez)
    cb.jedzenie_nie_do = s.t + 100000
    stop12c = TMP / f"STOP{_n[0]}"
    if pre(s, cb, w):
        bieg(s, cb, w, maks=5000)
    kon = ev(s, "wyprawa_koniec")
    sprawdz("12i limit czasu w marszu do depo: alarm + STOP", kon and kon[-1]["wynik"] == "blad" and s.alarmy and stop12c.exists(), kon)
    # walka i ucieczka w drodze mają pierwszeństwo, wyprawa dochodzi
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez)
    krok_dokladny(cb)
    cb.jedzenie_nie_do = s.t + 100000
    stop12d = TMP / f"STOP{_n[0]}"
    st12 = {"walka": 0, "uciekl": 0}
    def fn12(i):
        if w.aktywny and s.poz[2] == 9 and st12["walka"] < 20:
            s.cel = {"id": 77}; st12["walka"] += 1
        else:
            s.cel = None
        if w.aktywny and s.poz[2] == 7 and 5 < st12["uciekl"] < 20:
            s.ucieczka = True
        else:
            s.ucieczka = False
        if w.aktywny and s.poz[2] == 7:
            st12["uciekl"] += 1
    n, wyst = bieg(s, cb, w, maks=12000, fn=fn12) if pre(s, cb, w) else (0, False)
    sprawdz("12j walka i ucieczka po drodze: wyprawa mimo to dochodzi do depo i kończy STOP-em",
            wyst and st12["walka"] >= 5 and st12["uciekl"] > 20 and tuple(s.poz) == DEPO and stop12d.exists(), (st12, s.poz))
    # restart w środku marszu wznawia i kończy w depo
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez)
    krok_dokladny(cb)
    cb.jedzenie_nie_do = s.t + 100000
    pre(s, cb, w)
    for i in range(3000):
        s.t += 0.3; s.wall += 0.3
        cb.ruch_poz = tuple(s.poz)
        w.tick()
        if s.poz[2] == 7 and len(s.pietra) > 3:
            break
    st_r = json.loads(w.plik_stanu.read_text())
    w.przerwij("STOP")
    cbr = krok_dokladny(CB(s))
    logr = []
    opsr = Ops(s); opsr.log = logr.append
    stopr = TMP / "STOP_depo_r"
    wr = W.Wyprawa(cbr, opsr, konf=konf_depo(), log=logr.append, plik_stanu=w.plik_stanu, plik_sklepow=sp_bez,
                   plik_npc=TMP / "npc_depo_r.json", plik_stop=stopr, czas=lambda: s.wall)
    startr = False
    for i in range(9000):
        s.t += 0.3; s.wall += 0.3
        cbr.ruch_poz = tuple(s.poz); cbr.ostatnie_stwory = []
        wr.tick()
        if wr.aktywny:
            startr = True
        elif startr:
            break
    sprawdz("12k restart w środku marszu (stan: depo): wznowiona, dochodzi do depo, STOP, bez powrotu na spot",
            st_r.get("aktywna") and st_r.get("potrzeby") == {"depo": True} and startr
            and any("WZNOWIONA" in l for l in logr) and tuple(s.poz) == DEPO and stopr.exists() and s.mowa == [],
            (st_r.get("aktywna"), logr[-3:], s.poz))
finally:
    _pw.powiadom = _stare
ok_, bl_ = pokretla.waliduj({"WYPRAWA_TYLKO_DEPO": 1}, {"WYPRAWA_TYLKO_DEPO": 0})
sprawdz("12l analityk nie włączy WYPRAWA_TYLKO_DEPO", not ok_ and len(bl_) == 1, f"{ok_} {bl_}")
sprawdz("12m cavebot.WYPRAWA_TYLKO_DEPO domyślnie 0", cavebot.WYPRAWA_TYLKO_DEPO == 0)

# --- 13. start wyprawy do depo w walce (WYPRAWA_DEPO_W_WALCE) ---
_pw.powiadom = lambda *a, **kw: None
for opis13, wl13, oczek13 in (("13a w walce startuje (potwory obok, cel, głód)", 1, True),
                             ("13b WYPRAWA_DEPO_W_WALCE=0: w walce nie startuje", 0, False)):
    s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(WYPRAWA_DEPO_W_WALCE=wl13), sklepy=sp_bez)
    krok_dokladny(cb)
    cb.jedzenie_nie_do = s.t + 100000
    s.stwory.append({"id": 77, "nazwa": "Troll", "gracz": False, "x": s.poz[0] + 1, "y": s.poz[1], "z": s.poz[2], "hp": 100})
    s.cel = s.stwory[-1]
    wyn13 = False
    for _ in range(5):
        s.t += 20
        s.wall += 20
        cb.ruch_poz, cb.ostatnie_stwory, cb.cel = tuple(s.poz), list(s.stwory), s.cel
        cb.ucieczka = False
        wyn13 = wyn13 or w.okazja_w_walce(s.t)
    sprawdz(f"{opis13}", wyn13 == oczek13 and cb.wypad_aktywny == oczek13, (wyn13, cb.wypad_aktywny))
sprawdz("13c cavebot.WYPRAWA_DEPO_W_WALCE w pokretla.ZAKRESY", "WYPRAWA_DEPO_W_WALCE" in pokretla.ZAKRESY)

# --- 14. składanie UH w depo na początku zwykłej wyprawy (WYPRAWA_DEPO_ZLOZ) ---
_pw.powiadom = lambda *a, **kw: None
class OpsZ(Ops):
    zlozone = []
    def zloz_w_depo(o, pozycja):
        OpsZ.zlozone.append(tuple(pozycja()))
        o.s.t += 3
        return {"otwarte": True, "przeniesione": 4, "powod": None}
kk14 = konf_glod(); kk14.WYPRAWA_DEPO_ZLOZ = 1
s, cb, w, k = nowy(jedzenie=0, konf=kk14)
krok_dokladny(cb)
cb.jedzenie_nie_do = s.t + 100000
w.ops = OpsZ(s)
w.ops.log = w.logi.append
st14 = pre(s, cb, w)
ids14 = [st["id"] for st in w.w["stops"]] if w.w else None
sprawdz("14a start: pierwszy przystanek depo_zloz, potem frodo/xodet", st14 and ids14 and ids14[0] == "depo_zloz" and "frodo" in ids14, ids14)
n, wyst = bieg(s, cb, w, maks=14000)
sprawdz("14b skladanie wykonane raz, na polu depo", len(OpsZ.zlozone) == 1 and OpsZ.zlozone[0] == (32343, 32226, 7), OpsZ.zlozone)
sprawdz("14c po depo wyprawa kupuje ham u Frodo i konczy", wyst and s.plecak.get(3582, 0) > 0, (s.plecak, s.mowa[:6]))
kk14b = konf_glod(); kk14b.WYPRAWA_DEPO_ZLOZ = 0
OpsZ.zlozone.clear()
s, cb, w, k = nowy(jedzenie=0, konf=kk14b)
cb.jedzenie_nie_do = s.t + 100000
w.ops = OpsZ(s); w.ops.log = w.logi.append
pre(s, cb, w)
sprawdz("14d knob 0: brak przystanku depo_zloz", w.w and all(st["id"] != "depo_zloz" for st in w.w["stops"]), w.w and [st["id"] for st in w.w["stops"]])
sprawdz("14e WYPRAWA_DEPO_ZLOZ w pokretla.ZAKRESY", "WYPRAWA_DEPO_ZLOZ" in pokretla.ZAKRESY)

# --- 15. P7 (14.10): dojście bez wyprawy, blanki w trybie depo, pamięć depo --------------------
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1))
cb.dojscie_aktywne = True
sprawdz("15a dojscie_aktywne: _blokada_startu = 'dojscie'", w._blokada_startu(s.t, tuple(s.poz), []) == "dojscie")
sprawdz("15a2 dojście: wyprawa nie startuje mimo blanków 0", not pre(s, cb, w, 6))
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1, WYPRAWA_DEPO_BLANKI=0))
sprawdz("15b tryb depo, blanki 0, zapas ok, WYPRAWA_DEPO_BLANKI=0: brak wyprawy", not pre(s, cb, w, 6) and not cb.wypad_aktywny)
sprawdz("15b2 jednorazowa notatka o braku blanków", sum("brak blanków" in l for l in w.logi) == 1, w.logi[-3:])
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1, WYPRAWA_DEPO_BLANKI=1))
sprawdz("15c WYPRAWA_DEPO_BLANKI=1: wyprawa 'depo:blanki' startuje", pre(s, cb, w, 6) and w.powod.startswith("wyprawa:depo:blanki"), w.powod)
# N2 (14.10): bez żadnego pokrętła z na_zywo (konf nie ma WYPRAWA_DEPO_BLANKI) domyślna = 1: brak blanków = depo
sprawdz("15c2 domyślne WYPRAWA_DEPO_BLANKI=1 w cavebot.py i wyprawa.DOMYSLNE", cavebot.WYPRAWA_DEPO_BLANKI == 1
        and W.DOMYSLNE["WYPRAWA_DEPO_BLANKI"] == 1)
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1))
sprawdz("15c3 tryb depo, 0 blanków, zapas ok, bez pokręteł z na_zywo: 'depo:blanki' startuje",
        not hasattr(k, "WYPRAWA_DEPO_BLANKI") and pre(s, cb, w, 6) and w.powod.startswith("wyprawa:depo:blanki"), w.powod)
# N2: "domyślna" w logu hot reload = wartość z kodu także dla drugiej instancji Pokretla w tym samym procesie
_m = types.SimpleNamespace(PIETRA_LOPATA=1, WYPRAWA_DEPO_BLANKI=1)
_lg = []
_p1 = pokretla.Pokretla(_m, plik=TMP / "nz15.json", log=_lg.append)
_p1.zastosuj({"PIETRA_LOPATA": 0})
_p2 = pokretla.Pokretla(_m, plik=TMP / "nz15b.json", log=_lg.append)
_p2.zastosuj({"PIETRA_LOPATA": 1})
sprawdz("15c4 druga instancja Pokretla: domyślna z kodu (1), nie nadpisana (0)", _p2.domyslne["PIETRA_LOPATA"] == 1
        and any("PIETRA_LOPATA: 1 (domyślna 1)" in l for l in _lg), _lg)
_p2.zastosuj({})
sprawdz("15c5 powrót do domyślnej przywraca wartość z kodu", _m.PIETRA_LOPATA == 1, _m.PIETRA_LOPATA)
stan15 = TMP / "stan15.json"
stan15.write_text(json.dumps({"depo_powody": ["blanki"], "depo_blanki": 0, "nast_wall": 0}))
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1, WYPRAWA_DEPO_BLANKI=1), stan=stan15)
sprawdz("15d pamięć depo: te same braki jak przy ostatnim depo = brak wyprawy (log)", not pre(s, cb, w, 6)
        and any("jak przy ostatnim depo" in l for l in w.logi), w.logi[-3:])
sprawdz("15e nowe pokrętła P7 w pokretla.ZAKRESY", all(x in pokretla.ZAKRESY for x in (
    "WYPRAWA_DEPO_BLANKI", "WYPRAWA_PO_DEPO_S", "WYPRAWA_PO_DOJSCIU_S", "DOJSCIE_WALKA_PRZEJSCIE_S",
    "DOJSCIE_BEZ_UNIKANIA_POL", "DOJSCIE_PROBY", "DOJSCIE_PAUZA_PROBY_S")) and all(hasattr(cavebot, x) for x in (
    "WYPRAWA_DEPO_BLANKI", "WYPRAWA_PO_DEPO_S", "WYPRAWA_PO_DOJSCIU_S", "DOJSCIE_WALKA_PRZEJSCIE_S",
    "DOJSCIE_BEZ_UNIKANIA_POL", "DOJSCIE_PROBY", "DOJSCIE_PAUZA_PROBY_S")))

# --- 16. N5: fałszywy głód przy niewidocznych kontenerach, wznowienie po restarcie ---------------
def stan_depo(powod="depo:glod", **extra):
    p = TMP / f"n5_{_n[0]}.json"
    _n[0] += 1
    d = {"aktywna": True, "przerwana": True, "baza": "troll", "k": 0, "faza": "do", "powod": powod,
         "potrzeby": {"depo": True}, "t_wall": 5_000_000.0 - 10, "kupione": {}}
    d.update(extra)
    p.write_text(json.dumps(d))
    return p

st16 = stan_depo()
s, cb, w, k = nowy(jedzenie=3, stan=st16, konf=konf_depo(), sklepy=sp_bez)
w.tick()
sprawdz("16a stan depo:glod + zapas 3 + kontenery widoczne: brak wznowienia, stan wygaszony",
        not cb.wypad_aktywny and w.w is None and json.loads(st16.read_text()).get("aktywna") is False
        and json.loads(st16.read_text()).get("wynik") == "powod_ustal"
        and not any("WZNOWIONA" in l for l in w.logi), w.logi[-3:])
st16b = stan_depo()
kk = konf_depo(WYPRAWA_WZNOW_WALIDUJ=0)
s, cb, w, k = nowy(jedzenie=3, stan=st16b, konf=kk, sklepy=sp_bez, poz=DEPO)
w._powod_ustal = lambda st: (_ for _ in ()).throw(AssertionError("walidacja przy pokrętle 0"))
try:
    w.tick()
    ok16b = True
except AssertionError:
    ok16b = False
sprawdz("16b WYPRAWA_WZNOW_WALIDUJ=0: walidacja pominięta (dawne zachowanie)", ok16b)
s, cb, w, k = nowy(jedzenie=0, stan=stan_depo(), konf=konf_depo(), sklepy=sp_bez)
sprawdz("16c zapas 0: powód nadal zachodzi, nie kasujemy", w._powod_ustal(json.loads(w.plik_stanu.read_text())) is False)
s, cb, w, k = nowy(jedzenie=0, stan=stan_depo("depo:glod+blanki"), konf=konf_depo(), sklepy=sp_bez)
s.plecak[3582] = 9
sprawdz("16d powód z blankami: nie kasujemy", w._powod_ustal(json.loads(w.plik_stanu.read_text())) is False)
s, cb, w, k = nowy(jedzenie=3, stan=stan_depo(faza="z"), konf=konf_depo(), sklepy=sp_bez)
sprawdz("16e faza powrotu: nie kasujemy", w._powod_ustal(json.loads(w.plik_stanu.read_text())) is False)
s, cb, w, k = nowy(jedzenie=3, stan=stan_depo(), konf=konf_depo(), sklepy=sp_bez)
w.ops.plecak = lambda: None
sprawdz("16f kontenery niewidoczne: nie umiemy zweryfikować, nie kasujemy",
        w._powod_ustal(json.loads(w.plik_stanu.read_text())) is False)
# kontenery niewidoczne: cb zgłasza odczyt wątpliwy -> brak glod_potw i brak powodu "glod"
s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez)
cb.jedzenie_nie_do = s.t + 1000
cb.jedzenie_odczyt_watpliwy = lambda t: True
cb.jedzenie_znane_brak = lambda t: False
sprawdz("16g wątpliwy odczyt: brak glod_potw i brak startu depo", not pre(s, cb, w, 6) and w.glod_potw_do == float("-inf"), w.glod_potw_do)
# glod_potw wygasa, gdy zapas nieczytelny dłużej niż GLOD_ZAPAS_WAZNY_S
s, cb, w, k = nowy(jedzenie=0, konf=konf_depo(), sklepy=sp_bez)
cb.jedzenie_nie_do = s.t + 100
pre(s, cb, w, 1)
sprawdz("16h głód potwierdzony przy czytelnym plecaku", w.glod_potw_do > s.t)
cb.jedzenie_nie_do = float("-inf")
w.ops.plecak = lambda: None
s.t += 500
w.sprawdzono_w = float("-inf"); w.nast_wyprawa = float("-inf")
for _ in range(2):
    s.t += 20; cb.ruch_poz = tuple(s.poz)
    w._okazja_wyprawa(s.t)
sprawdz("16i plecak nieczytelny > GLOD_ZAPAS_WAZNY_S: glod_potw_do skasowany", w.glod_potw_do == float("-inf"), w.glod_potw_do)
sprawdz("16j nowe pokrętła N5 w ZAKRESY/cavebot", all(x in pokretla.ZAKRESY for x in (
    "JEDZENIE_BRAK_WALIDUJ", "JEDZENIE_BRAK_PROBY", "GLOD_ZAPAS_WAZNY_S", "WYPRAWA_WZNOW_WALIDUJ"))
    and all(hasattr(cavebot, x) for x in ("JEDZENIE_BRAK_WALIDUJ", "JEDZENIE_BRAK_PROBY", "GLOD_ZAPAS_WAZNY_S",
                                          "WYPRAWA_WZNOW_WALIDUJ")))

# --- N9: blanki do bagu poza wyprawą ---
def _auto(stan=(5, 3), **kw):
    s, cb, w, k = nowy(**kw)
    wyw = []
    w.ops.blanki_i_miejsce = lambda: stan
    w.ops.przenies_runy = lambda: (wyw.append(1), 5)[1]
    cb.ruch_poz = tuple(s.poz)
    return s, cb, w, k, wyw

s, cb, w, k, wyw = _auto()
w._blanki_auto(s.t)
sprawdz("17a start: blanki w plecaku + wolne pole -> przeniesione raz", len(wyw) == 1, wyw)
w._blanki_auto(s.t + 60)
sprawdz("17b przed upływem BLANKI_AUTO_BAG_MIN brak ponowienia", len(wyw) == 1, wyw)
w._blanki_auto(s.t + 601)
sprawdz("17c po 10 min druga próba", len(wyw) == 2, wyw)
s, cb, w, k, wyw = _auto(stan=(5, 0))
w._blanki_auto(s.t)
sprawdz("17d brak wolnego pola: bez ruchu myszy i jedna linia logu", not wyw and
        sum("brak wolnego widocznego pola" in l for l in w.logi) == 1, (wyw, w.logi))
s, cb, w, k, wyw = _auto(stan=(0, 3))
w._blanki_auto(s.t)
sprawdz("17e brak blanków w plecaku: nic", not wyw)
s, cb, w, k, wyw = _auto()
cb.cel = {"x": 1}
sprawdz("17f w walce nie rusza i nie zużywa terminu", not w._blanki_auto(s.t) and not wyw and w._blanki_auto_t is None)
cb.cel = None
w._blanki_auto(s.t)
sprawdz("17g po walce przenosi", len(wyw) == 1)
k.BLANKI_AUTO_BAG = 0
s, cb, w, k, wyw = _auto()
k.BLANKI_AUTO_BAG = 0
w._blanki_auto(s.t)
sprawdz("17h pokrętło BLANKI_AUTO_BAG=0 wyłącza", not wyw)
sprawdz("17i pokrętła w ZAKRESY/cavebot", all(x in pokretla.ZAKRESY for x in ("BLANKI_AUTO_BAG", "BLANKI_AUTO_BAG_MIN"))
        and all(hasattr(cavebot, x) for x in ("BLANKI_AUTO_BAG", "BLANKI_AUTO_BAG_MIN")))

# --- N10: kup_u_npc ---
class OpsKup:
    def __init__(o, odp):
        o.odp, o.wys, o.q = odp, [], []
    def wiadomosci(o):
        w, o.q = o.q, []
        return w
    def czat(o, t):
        o.wys.append(t)
        for p, a in o.odp:
            if t.startswith(p):
                o.q.append({"autor": "Xodet", "kanal": "Default", "tekst": a})

def _kup(odp, n=20, lim=500):
    o = OpsKup(odp)
    return W.kup_u_npc("Xodet", "blank rune", n, lim, ops=o, log=lambda *a: None, czekaj_s=0.3, spij=lambda x: None), o
ODP = [("hi", "Oh, please come in, Jointoramix!"), ("buy", "Do you want to buy 20 blank rune for 200 gold?"),
       ("yes", "Here you are.")]
r, o = _kup(ODP)
sprawdz("18a oferta 200 gp przy limicie 500: yes", r["ok"] and r["oferta"] == (20, 200) and o.wys[-1] == "yes", (r, o.wys))
r, o = _kup(ODP, lim=150)
sprawdz("18b limit 150 odrzuca 200 gp (limit parametrem)", not r["ok"] and r["powod"] == "za_drogo" and o.wys[-1] == "no", (r, o.wys))
r, o = _kup(ODP, lim=None)
sprawdz("18c limit None = bez limitu", r["ok"])
r, o = _kup([])
sprawdz("18d brak powitania", r["powod"] == "brak_powitania" and o.wys == ["hi"], (r, o.wys))
r, o = _kup([ODP[0]])
sprawdz("18e brak oferty", r["powod"] == "brak_oferty", r)
sprawdz("18f Xodet zweryfikowany w wyprawa_sklepy.json",
        json.loads((Path(W.__file__).parent / "trasy" / "wyprawa_sklepy.json").read_text())["przystanki"]["xodet"]["zweryfikowane"] is True)

# --- 19. ręczne "Wróć do miasta" (plik WROC, 19.10): tylko depo na jedną wyprawę, bezpieczniki zostają ---
import subprocess
import time as _time
_pw.powiadom = lambda *a, **kw: None
GOB_DO, GOB_Z, _ = BAZA_PK = W.punkty_bazy(nazwy=W.BAZY_PK)["gobliny_edron"]
GOB_DEPO = tuple(GOB_DO[-1])
GOB_BLISKO = (33167, 31813, 8)                 # piętro depo Edron (po schodach), ~20 pól od pola depo; atrapa świata nie zna
#   przejścia z7 -> z8 przy depo (nagranie omija pole dziury (33167,31812,7), plan ma tam znane ostrzeżenie), więc dojście sprawdzamy stąd
ROOK_START = (32021, 32159, 11)                # początek trasy rooka kanały z11 (do_miasta.json): teraz w PLANY_PK
POZA_PLANEM = (32300, 32400, 7)                # 21.10: pozycja >300 pól od najbliższej trasy (żaden plan, test brak-planu)


def konf_wroc(**kw):
    kk = Konf(); kk.WYPRAWA_AKTYWNA = 0          # domyślnie jak na bocie bez trybu wyprawy: ręczne wywołanie ma działać
    for a, b in kw.items():
        setattr(kk, a, b)
    return kk


def wroc_swiat(poz=START, plan=None, **kw):
    s, cb, w, k = nowy(poz=poz, konf=kw.pop("konf", None) or konf_wroc(), sklepy=sp_bez, jedzenie=kw.pop("jedzenie", 9), **kw)
    krok_dokladny(cb)
    if plan:
        s.wej.update(przejscia(plan))
    cb.ruch_poz = tuple(s.poz)
    plik = w._plik_wroc()
    plik.write_text("")
    return s, cb, w, k, plik


def tyk(s, cb, w, dt=1.0):
    s.t += dt; s.wall += dt
    cb.ruch_poz = tuple(s.poz); cb.ostatnie_stwory = list(s.stwory); cb.cel = s.cel
    return w._okazja(s.t)


pw19 = []
_pw.powiadom = lambda *a, **kw: pw19.append(a)
try:
    # a. start w spokoju, także przy WYPRAWA_AKTYWNA=0; bez potwierdzeń, pierwszy odczyt wystarcza; plik znika po ruszeniu
    s, cb, w, k, plik = wroc_swiat()
    sprawdz("19a0 baza: WYPRAWA_AKTYWNA=0 (bez WROC wyprawa nie rusza)", not (plik.unlink() or tyk(s, cb, w)) and not cb.wypad_aktywny)
    plik.write_text("")
    start = tyk(s, cb, w)
    sprawdz("19a WROC + AKTYWNA=0, spokój: jeden obieg startuje wyprawę 'depo:reczny' (tylko depo, flaga reczny)",
            start and cb.wypad_aktywny and w.powod == "wyprawa:depo:reczny" and w.w["potrzeby"] == {"depo": True, "reczny": True}
            and [st["id"] for st in w.w["stops"]] == ["depo"], (w.powod, w.w and w.w["potrzeby"]))
    sprawdz("19b plik WROC znika po ruszeniu (nie przed), a pokrętło globalne nie zostaje ruszone",
            not plik.exists() and k.WYPRAWA_TYLKO_DEPO == 0 and k.WYPRAWA_AKTYWNA == 0 and w._wroc_od is None)
    sprawdz("19c powiadomienie o ruszeniu bez 'brak jedzenia'", any(a[0] == "Wróć do miasta: ruszam" for a in pw19)
            and not any("głód" in a[1].lower() for a in pw19 if a[0].startswith("Wróć")), pw19)

    # b. po dojściu STOP + powiadomienie, bez zakupów (trasa goblinów Edron, plan wybrany po położeniu)
    pw19.clear()
    s, cb, w, k, plik = wroc_swiat(poz=GOB_DO[0], plan=GOB_DO)
    start = tyk(s, cb, w)
    sprawdz("19d położenie w jaskini goblinów: plan gobliny_edron, cel = pole depo Edron",
            start and w.w["baza"] == "gobliny_edron" and tuple(w.w["stops"][0]["stoi"]) == GOB_DEPO, (w.w and w.w["baza"]))
    pw19.clear()
    s, cb, w, k, plik = wroc_swiat(poz=GOB_BLISKO)
    stop = w.plik_stop
    plecak0 = dict(s.plecak)
    start = tyk(s, cb, w)
    n, wyst = bieg(s, cb, w, maks=12000)
    kon = ev(s, "wyprawa_koniec")
    sprawdz("19e dojście: koniec 'depo', STOP, stan wyczyszczony, wypad nieaktywny, żadnych zakupów ani powrotu",
            wyst and tuple(s.poz) == GOB_DEPO and kon and kon[-1]["wynik"] == "depo" and stop.exists() and w.w is None
            and not cb.wypad_aktywny and s.mowa == [] and s.plecak == plecak0 and cb.wroty == [] and not s.alarmy,
            (s.poz, kon, stop.exists(), s.mowa, s.alarmy))
    sprawdz("19f powiadomienie 'jestem w depo' (critical), bez 'brak jedzenia'; plik WROC nie wrócił",
            any(a[0] == "Wyprawa: jestem w depo" and a[2] == "critical" and "brak jedzenia" not in a[1] for a in pw19)
            and not plik.exists(), pw19)
    stop.unlink()

    # c. WYPRAWA_DEPO_POWROT=1 nie zawraca ręcznego wywołania na spot (bezpiecznik: STOP w depo)
    s, cb, w, k, plik = wroc_swiat(poz=GOB_BLISKO, konf=konf_wroc(WYPRAWA_DEPO_POWROT=1))
    stop = w.plik_stop
    tyk(s, cb, w)
    n, wyst = bieg(s, cb, w, maks=12000)
    sprawdz("19g WYPRAWA_DEPO_POWROT=1: ręczne wywołanie i tak staje w depo (STOP), nie wraca na spot",
            wyst and tuple(s.poz) == GOB_DEPO and stop.exists() and w.faza != "z", (s.poz, w.faza, stop.exists()))
    stop.unlink()

    # d. plan po położeniu: Thais (troll) działa, rook (inne miasto) to brak planu = komunikat + plik znika
    s, cb, w, k, plik = wroc_swiat(poz=START)
    sprawdz("19h położenie w jaskini trolli: plan troll (depo Thais)", tyk(s, cb, w) and w.w["baza"] == "troll", w.w and w.w["baza"])
    pw19.clear()
    s, cb, w, k, plik = wroc_swiat(poz=POZA_PLANEM)
    r = tyk(s, cb, w)
    sprawdz("19i poza zasięgiem planów: brak depo -> bez startu, powiadomienie 'nie mogę ruszyć', plik WROC usunięty, bez ponawiania",
            not r and not cb.wypad_aktywny and not plik.exists() and any("nie mogę ruszyć" in a[1] for a in pw19)
            and not tyk(s, cb, w) and not tyk(s, cb, w, 400), (pw19, w.logi[-3:]))
    sprawdz("19i2 nieudane ręczne wywołanie nie odkłada automatycznych wypraw (nast_wyprawa bez zmian)",
            w.nast_wyprawa == float("-inf"), w.nast_wyprawa)

    # e. bezpieczniki: walka, niskie HP, PK/gracz obok, zablokowany -> bez startu, plik zostaje; po limicie komunikat
    def zablokowane(opis, przygotuj):
        pw19.clear()
        s, cb, w, k, plik = wroc_swiat()
        przygotuj(s, cb, w)
        wyn = [tyk(s, cb, w) for _ in range(5)]
        trzyma = not any(wyn) and not cb.wypad_aktywny and plik.exists() and not pw19
        for _ in range(2):
            tyk(s, cb, w, 100.0)                # 200 s > WROC_BLOKADA_MAX_S (180 s)
        sprawdz(f"19j {opis}: bez startu, plik czeka, po limicie powiadomienie 'nie mogę ruszyć' i plik usunięty",
                trzyma and not cb.wypad_aktywny and not plik.exists() and any("nie mogę ruszyć" in a[1] for a in pw19),
                (wyn, plik.exists(), pw19, w.logi[-2:]))
        return s, cb, w, plik

    def walka(s, cb, w):
        s.stwory.append({"id": 77, "nazwa": "Troll", "gracz": False, "x": s.poz[0] + 1, "y": s.poz[1], "z": s.poz[2], "hp": 100})
        s.cel = s.stwory[-1]
    zablokowane("w walce (cel)", walka)
    zablokowane("niskie HP (40%)", lambda s, cb, w: setattr(s, "hp", 40))
    zablokowane("obcy gracz obok (PK)", lambda s, cb, w: s.stwory.append(
        {"id": 5, "nazwa": "Zly", "gracz": True, "x": s.poz[0] + 3, "y": s.poz[1], "z": s.poz[2], "hp": 100}))
    zablokowane("wyprawa zablokowana (STOP/alarm/PK)", lambda s, cb, w: setattr(w, "zablokowany", True))
    zablokowane("blokada po porażce wypadu", lambda s, cb, w: setattr(w, "blokada_do", s.t + 100000))
    zablokowane("ucieczka", lambda s, cb, w: setattr(s, "ucieczka", True) or setattr(cb, "ucieczka", True))

    # f. blokada mija przed limitem: rusza w pierwszej spokojnej chwili, nie czeka na limit ani na cooldown
    s, cb, w, k, plik = wroc_swiat()
    s.hp = 40
    w.nast_wyprawa = s.t + 100000                # cooldown automatycznych wypraw nie dotyczy ręcznego wywołania
    pierwsze = [tyk(s, cb, w) for _ in range(3)]
    s.hp = 100
    sprawdz("19k HP wraca w limicie: wyprawa rusza mimo cooldownu nast_wyprawa, plik znika po ruszeniu",
            not any(pierwsze) and plik.exists() and tyk(s, cb, w) and not plik.exists() and cb.wypad_aktywny)

    # g. w walce (okazja_w_walce, WYPRAWA_DEPO_W_WALCE=1) ręczne wywołanie nie rusza nawet przy AKTYWNA=0 i AKTYWNA=1
    for akt in (0, 1):
        s, cb, w, k, plik = wroc_swiat(konf=konf_wroc(WYPRAWA_AKTYWNA=akt, WYPRAWA_DEPO_W_WALCE=1))
        walka(s, cb, w)
        cb.ruch_poz, cb.ostatnie_stwory, cb.cel = tuple(s.poz), list(s.stwory), s.cel
        wyn = [w.okazja_w_walce(s.t + i) for i in range(4)]
        sprawdz(f"19l okazja_w_walce przy AKTYWNA={akt}: ręczne wywołanie nie startuje w walce, plik zostaje",
                not any(wyn) and not cb.wypad_aktywny and plik.exists(), wyn)

    # g2. ciągła walka: limit WROC_BLOKADA_MAX_S płynie także w okazja_w_walce (przeplot z _okazja), potem komunikat i brak pliku
    pw19.clear()
    s, cb, w, k, plik = wroc_swiat(konf=konf_wroc(WYPRAWA_DEPO_W_WALCE=1))
    walka(s, cb, w)
    wyn = []
    for i in range(12):
        s.t += 20; s.wall += 20
        cb.ruch_poz, cb.ostatnie_stwory, cb.cel = tuple(s.poz), list(s.stwory), s.cel
        wyn.append(w.okazja_w_walce(s.t) if i % 2 else w._okazja(s.t))
    sprawdz("19l2 ciągła walka (240 s, przeplot okazja_w_walce/_okazja): bez startu, powiadomienie 'nie mogę ruszyć', plik usunięty",
            not any(wyn) and not cb.wypad_aktywny and not plik.exists() and any("nie mogę ruszyć" in a[1] for a in pw19),
            (wyn, plik.exists(), pw19))

    # g3. wyjątek przy starcie kończy zlecenie (nie ponawia co obieg); nieudany start nie kasuje potwierdzonego głodu
    pw19.clear()
    s, cb, w, k, plik = wroc_swiat()
    def _wyjatek(*a, **kw):
        raise RuntimeError("test")
    w._start_wyprawa = _wyjatek
    r = tyk(s, cb, w)
    sprawdz("19l3 wyjątek w _start_wyprawa: zlecenie zakończone komunikatem, plik usunięty, bez ponawiania",
            not r and not plik.exists() and any("nie mogę ruszyć" in a[1] and "test" in a[1] for a in pw19) and not tyk(s, cb, w), pw19)
    s, cb, w, k, plik = wroc_swiat(poz=POZA_PLANEM)
    w.glod_potw_do = s.t + 5000
    glod0 = w.glod_potw_do
    tyk(s, cb, w)
    sprawdz("19l4 nieudany ręczny start (poza planem) nie kasuje potwierdzonego głodu (CZEKAJ_NA_GLOD)", w.glod_potw_do == glod0, w.glod_potw_do)

    # h. anulowanie: usunięcie pliku (wroc.sh --anuluj) przed ruszeniem; zlecenie nie wraca samo
    pw19.clear()
    s, cb, w, k, plik = wroc_swiat()
    s.hp = 40
    tyk(s, cb, w)
    zlecenie = w._wroc_od is not None
    plik.unlink()                                 # to robi ./wroc.sh --anuluj
    s.hp = 100
    sprawdz("19m --anuluj: po usunięciu pliku wyprawa nie rusza i nie ma śladu zlecenia",
            zlecenie and not tyk(s, cb, w) and not cb.wypad_aktywny and w._wroc_od is None and not pw19)

    # i. wznowienie po restarcie w marszu ręcznego wywołania (bez pliku WROC): dochodzi do depo i staje
    s, cb, w, k, plik = wroc_swiat(poz=GOB_BLISKO, konf=konf_wroc(WYPRAWA_DEPO_POWROT=1))
    tyk(s, cb, w)
    for i in range(2):                            # kilka obiegów marszu, potem "restart bota"
        s.t += 0.3; s.wall += 0.3
        cb.ruch_poz = tuple(s.poz); cb.ostatnie_stwory = []
        w.tick()
    st_r = json.loads(w.plik_stanu.read_text())
    w.przerwij("STOP")
    cbr = krok_dokladny(CB(s))
    logr = []
    opsr = Ops(s); opsr.log = logr.append
    stopr = TMP / "STOP_wroc_r"
    wr = W.Wyprawa(cbr, opsr, konf=konf_wroc(WYPRAWA_DEPO_POWROT=1), log=logr.append, plik_stanu=w.plik_stanu, plik_sklepow=sp_bez,
                   plik_npc=TMP / "npc_wroc_r.json", plik_stop=stopr, czas=lambda: s.wall)
    startr = False
    for i in range(12000):
        s.t += 0.3; s.wall += 0.3
        cbr.ruch_poz = tuple(s.poz); cbr.ostatnie_stwory = []
        wr.tick()
        if wr.aktywny:
            startr = True
        elif startr:
            break
    sprawdz("19n restart w marszu: stan 'reczny' przeżywa, wznowiona wyprawa staje w depo (STOP) mimo DEPO_POWROT=1",
            st_r.get("aktywna") and (st_r.get("potrzeby") or {}).get("reczny") and startr and tuple(s.poz) == GOB_DEPO
            and stopr.exists() and s.mowa == [], (st_r.get("potrzeby"), logr[-3:], s.poz))
finally:
    _pw.powiadom = _stare

# --- 19o. wroc.sh: odmowa bez bota, z atrapą bota, --anuluj (bez gry i bez gniazd; notify-send podmieniony) ---
_RID = "wroctest"
_KAT = Path(__file__).resolve().parent.parent
_INST = _KAT / "instancje" / _RID
_BIN = TMP / "bin"
_BIN.mkdir(exist_ok=True)
_NOT = TMP / "notify.log"
(_BIN / "notify-send").write_text(f'#!/bin/bash\necho "$*" >> {_NOT}\n')
(_BIN / "notify-send").chmod(0o755)
_env = dict(_os.environ, RETRONIC_ID=_RID, PATH=f"{_BIN}:{_os.environ['PATH']}")


def wroc_sh(*arg):
    return subprocess.run([str(_KAT / "wroc.sh"), *arg], env=_env, capture_output=True, text=True, timeout=20)


try:
    r = wroc_sh()
    sprawdz("19o wroc.sh bez bota: odmowa (kod 1), komunikat jak uruchomić, plik WROC nie powstaje",
            r.returncode == 1 and "uruchom" in r.stderr and not (_INST / "WROC").exists(), (r.returncode, r.stderr))
    sprawdz("19o2 odmowa idzie też powiadomieniem", _NOT.exists() and "Bot nie działa" in _NOT.read_text())
    _fake = subprocess.Popen(["python3", "-I", "-c", "import time; time.sleep(30)", "mozg.py"], env=_env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _time.sleep(0.5)
        r = wroc_sh()
        sprawdz("19p wroc.sh z (atrapą) bota tej instancji: zlecenie przyjęte, plik WROC w katalogu stanu instancji",
                r.returncode == 0 and (_INST / "WROC").exists() and "przyjęte" in r.stdout, (r.returncode, r.stdout, r.stderr))
        r = wroc_sh("--anuluj")
        sprawdz("19q wroc.sh --anuluj usuwa WROC (bot nie jest potrzebny)", r.returncode == 0 and not (_INST / "WROC").exists(), r.stdout)
    finally:
        _fake.kill()
        _fake.wait()
    r = wroc_sh("--anuluj")
    sprawdz("19r --anuluj bez zlecenia: kod 0 i informacja", r.returncode == 0 and "brak zlecenia" in r.stdout, r.stdout)
    r = wroc_sh("--zle")
    sprawdz("19s nieznany argument: kod 2 i użycie, bez pliku", r.returncode == 2 and "użycie" in r.stderr and not (_INST / "WROC").exists())

    # --- 19t. stary WROC nie przeżywa restartu: skrypty startu czyszczą go razem z STOP (wiersz z rm wykonany w piaskownicy) ---
    for _sk in ("uruchom.sh", "uruchom_trolle.sh", "serwis.sh"):
        _wiersz = next((l.strip() for l in (_KAT / _sk).read_text().splitlines() if l.strip().startswith('rm -f "$INST_STOP"')), "")
        _pia = Path(tempfile.mkdtemp())
        for _f in ("STOP", "STOP_RECZNY", "WROC"):
            (_pia / _f).write_text("")
        subprocess.run(["bash", "-c", _wiersz], env=dict(_os.environ, INST_STOP=str(_pia / "STOP"),
                       INST_STOP_RECZNY=str(_pia / "STOP_RECZNY"), INST_STAN=str(_pia)), check=False, timeout=10)
        sprawdz(f"19t {_sk}: wiersz czyszczący STOP kasuje też stary WROC (po restarcie bot nie rusza do depo)",
                "INST_STAN/WROC" in _wiersz and not any((_pia / f).exists() for f in ("STOP", "STOP_RECZNY", "WROC")), _wiersz)
finally:
    for _p in (_INST / "WROC", _INST):
        try:
            _p.unlink() if _p.is_file() else _p.rmdir()
        except OSError:
            pass

# --- 20. WYPRAWA_MARSZ_KLIK i WROC_REFILL (20.10): marsz klikiem w drodze do depo i automatyczny refill po dojściu ---
import marsz_klik
import refill_auto
from types import SimpleNamespace


class MapaFlagi:
    """Mapa do jednostkowych prób _marsz_klik: piętra 6..8 w całości chodliwe (flaga 1), `nad` nadpisuje pojedyncze pola."""

    def __init__(self, nad=None):
        self.nad = nad or {}

    def flagi(self, x, y, z):
        return self.nad.get((x, y, z), 1 if z in (6, 7, 8) else 0)


class KL:
    """Atrapa świata dla _marsz_klik: linia pól na z7 od (10,10); klik ustawia cel, a każdy odczyt pozycji przesuwa postać o pole.
    tryb: idzie | stoi (klik nic nie rusza) | pietro (klik zmienia piętro) | zasieg (klik rzuca ValueError) | wolno (nigdy nie dochodzi)."""

    def __init__(self, tryb="idzie", nad=None):
        self.t, self.poz, self.cel = 0.0, [10, 10, 7], None
        self.tryb, self.mapa = tryb, MapaFlagi(nad)
        self.klikniecia, self.esc, self.odczyty, self.stw, self.hp, self.ogien = [], 0, 0, [], 100.0, set()
        self.po_odczytach = None
        self.ucieczka = self.ostrozny = False
        self.postac = SimpleNamespace(nazwa="Ja", pozycja=self._pozycja, klawisz=self._klawisz)
        self.klik = self._klik

    ostatnie_stwory = property(lambda self: self.stw)

    def zegar(self):
        return self.t

    def spij(self, d):
        self.t += d

    def _klik(self, dx, dy):
        self.klikniecia.append((dx, dy))
        if self.tryb == "zasieg":
            raise ValueError("poza widokiem")
        self.cel = (self.poz[0] + dx, self.poz[1] + dy)

    def _pozycja(self):
        self.odczyty += 1
        if self.cel is not None and self.tryb == "idzie" and self.poz[:2] != list(self.cel):
            self.poz[0] += (self.cel[0] > self.poz[0]) - (self.cel[0] < self.poz[0])
            self.poz[1] += (self.cel[1] > self.poz[1]) - (self.cel[1] < self.poz[1])
        if self.tryb == "wolno" and self.cel is not None:       # postać przestępuje między dwoma polami: marsz trwa do limitu czasu
            self.poz[0] = 10 + (self.odczyty % 2)
        if self.tryb == "pietro" and self.cel is not None:
            self.poz[2], self.cel = 6, None
        if self.po_odczytach and self.odczyty == self.po_odczytach[0]:
            self.po_odczytach[1]()
        return tuple(self.poz)

    def _klawisz(self, k):
        if k == "Escape":
            self.esc += 1
            self.cel = None

    def gracz(self):
        return {"hp": self.hp, "max_hp": 100, "proc": self.hp}

    def stwory(self, maks_wiek=None):
        return list(self.stw)

    def _ogien_xy(self, z):
        return set(self.ogien)

    @staticmethod
    def gracz_grozny(m):
        return bool(m.get("czaszka"))


def klik_swiat(**kw):
    krok = kw.pop("krok", 1)                  # odstęp między punktami odcinka (nagrania bywają rzadkie: co 2+ pola)
    kl = KL(**{k: kw.pop(k) for k in ("tryb", "nad") if k in kw})
    s, cb0, w, k = nowy(konf=kw.pop("konf", None))
    w.cb, w.faza, w.pi = kl, "do", 0
    logi = []
    w.log = logi.append
    pkt = [(10 + krok * i, 10, 7) for i in range(12)]
    return kl, w, pkt, logi


def klikni(kl, w, pkt, poz=None):
    return w._marsz_klik(tuple(poz or kl.poz), pkt, kl.t)


def mob(x, y, **kw):
    return dict({"x": x, "y": y, "z": 7, "nazwa": "Goblin", "gracz": False, "hp": 100}, **kw)


schody = lambda x: {(x, 10, 7): 3, (x, 10, 6): 2}                # pole schodów na z7 z odpowiednikiem na z6

kl, w, pkt, logi = klik_swiat()
r = klikni(kl, w, pkt)
sprawdz("20a zwykłe pola: jeden klik w pole nr 5 (KLIK_MAKS_POL), postać dochodzi, pi przesunięte, licznik", r is True
        and kl.klikniecia == [(5, 0)] and tuple(kl.poz) == (15, 10, 7) and w.pi == 5 and w.klik_ile == 1, (r, kl.klikniecia, kl.poz, w.pi))
kl, w, pkt, logi = klik_swiat(nad=schody(15))
sprawdz("20b schody na polu nr 5: klik skrócony do pola nr 3 (prostokąt ścieżki z marginesem 1 nie może dotykać schodów)",
        klikni(kl, w, pkt) is True and kl.klikniecia == [(3, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat(nad=schody(13))
sprawdz("20c schody na polu nr 3: bez kliku (po skróceniu do pól przed schodami margines wciąż je obejmuje, <2 pola)",
        klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(nad={(12, 11, 7): 3, (12, 11, 6): 2})
sprawdz("20c2 schody tuż obok ścieżki (pole obok, nie na niej): bez kliku (margines 1)", klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(nad={(15, 14, 7): 3, (15, 14, 6): 2})
sprawdz("20c3 schody poza marginesem (4 pola od ścieżki): klik jak zwykle", klikni(kl, w, pkt) is True and kl.klikniecia == [(5, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat(nad=schody(11))
sprawdz("20d schody na polu nr 1: bez kliku", klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(nad={(12, 10, 7): 3, (12, 10, 6): 2})
pkt = [(10, 10, 7), (11, 9, 7), (12, 8, 7), (13, 9, 7), (14, 10, 7), (15, 10, 7)]       # nagranie omija dziurę (12,10), prosta przez nią prowadzi
sprawdz("20d2 objazd dziury: ścieżka omija pole (12,10), ale prostokąt ścieżki je obejmuje: bez kliku (klient poszedłby prosto)",
        klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(krok=2)
sprawdz("20d3 rzadkie punkty nagrania (co 2 pola): ścieżka zagęszczona, klik na 5 pól naprzód (nie na 5. punkt = 10 pól)",
        klikni(kl, w, pkt) is True and kl.klikniecia == [(5, 0)] and tuple(kl.poz) == (15, 10, 7), (kl.klikniecia, kl.poz))
kl, w, pkt, logi = klik_swiat(krok=2, nad={(13, 10, 7): 3, (13, 10, 6): 2})
sprawdz("20d4 rzadkie punkty, schody w luce między punktami (pole pośrednie): bez kliku", klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(krok=2, nad={(16, 10, 7): 3, (16, 10, 6): 2})
sprawdz("20d5 rzadkie punkty, schody dalej w luce: klik skrócony przed marginesem (do pola nr 4)", klikni(kl, w, pkt) is True and kl.klikniecia == [(4, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat(krok=3)
sprawdz("20d6 punkty co 3 pola: nadal klik do 5 pól, nie dalej niż zasięg widoku", klikni(kl, w, pkt) is True and kl.klikniecia == [(5, 0)] and abs(kl.klikniecia[0][0]) <= 6, kl.klikniecia)
kl, w, pkt, logi = klik_swiat(tryb="wolno")
klikni(kl, w, pkt)
sprawdz("20d7 limit czasu marszu liczony w polach: 5 pól = ok. 0,8 + 0,45 * 5 s (nie w punktach)", 3.0 <= kl.t <= 3.4, kl.t)
kl, w, pkt, logi = klik_swiat(krok=2, tryb="wolno")
klikni(kl, w, pkt)
sprawdz("20d8 to samo przy rzadkich punktach (co 2 pola): wciąż 5 pól, ten sam limit", 3.0 <= kl.t <= 3.4, kl.t)
kl, w, pkt, logi = klik_swiat()
kl.dziura_nauczona = lambda p: p[:2] == (13, 11)
sprawdz("20d9 dziura nauczona obok ścieżki (Cavebot ją zna, mapa nie): bez kliku", klikni(kl, w, pkt) is False and kl.klikniecia == [])
# --- klik „za siebie” (test na żywo 20.10, Johny): plan z zawrotem, indeks planu w tyle ---
def klik_plan(pkt, poz, pi=0):
    kl, w, _, logi = klik_swiat()
    kl.poz = list(poz)
    w.pi = pi
    return kl, w, pkt, logi


plan_odbicie = [(32483, 32301, 8), (32484, 32301, 8), (32485, 32301, 8), (32486, 32301, 8), (32485, 32301, 8), (32484, 32301, 8)]
kl, w, pkt, logi = klik_plan(plan_odbicie, (32485, 32301, 8), pi=2)
sprawdz("20e1 replay logu 08:51:55: plan wraca na pole postaci (odbicie), klik na własne pole odpada, ścieżka urywa się na zawrocie",
        klikni(kl, w, pkt) is False and kl.klikniecia == [], kl.klikniecia)
plan_ostroga = [(32490, 32262, 8), (32491, 32262, 8), (32492, 32261, 8), (32493, 32260, 8), (32492, 32261, 8), (32491, 32262, 8),
                (32490, 32262, 8), (32489, 32261, 8), (32488, 32260, 8), (32487, 32259, 8), (32486, 32258, 8), (32485, 32257, 8)]
kl, w, pkt, logi = klik_plan(plan_ostroga, (32490, 32262, 8), pi=6)
sprawdz("20e2 replay logu 08:55:07: postać na drugim przejściu pola (ostroga na wschód już za nią): klik na zachód/północ, nie na wschód",
        klikni(kl, w, pkt) is True and kl.klikniecia and kl.klikniecia[0][0] < 0 and kl.klikniecia[0][1] < 0 and w.pi >= 6, (kl.klikniecia, w.pi))
kl, w, pkt, logi = klik_plan(plan_ostroga, (32490, 32262, 8), pi=3)
sprawdz("20e3 ta sama ostroga, pi=3 (remis odległości): wybór późniejszego przejścia, klik na zachód",
        klikni(kl, w, pkt) is True and kl.klikniecia[0][0] < 0, kl.klikniecia)
kl, w, pkt, logi = klik_plan(plan_ostroga, (32490, 32262, 8), pi=0)
sprawdz("20e4 pi=0 (pierwsze przejście): klik na ostrogę jest naprzód po planie (3 pola na wschód), nie wstecz",
        klikni(kl, w, pkt) is True and kl.klikniecia[0][0] > 0, kl.klikniecia)
# postać przesunięta względem pi po udanym kliku: następny klik naprzód, indeks planu dogania pozycję
kl, w, pkt, logi = klik_swiat()
w.pi = 0
kl.poz = [13, 10, 7]                                      # postać stoi na punkcie nr 3, pi zostało na 0
sprawdz("20e5 pi w tyle o 3 punkty: klik naprzód (dx > 0), indeks planu wyrównany do pozycji",
        klikni(kl, w, pkt) is True and kl.klikniecia[0][0] > 0 and w.pi >= 3 + 4, (kl.klikniecia, w.pi))
kl, w, pkt, logi = klik_swiat(krok=2)
r1 = klikni(kl, w, pkt)
p1 = tuple(kl.poz)
kl.t += 1.0
r2 = klikni(kl, w, pkt)
sprawdz("20e6 rzadki plan: po kliku postać stoi na polu między punktami, a następny klik wciąż idzie naprzód (nie wstecz, nie w miejscu)",
        r1 is True and r2 is True and len(kl.klikniecia) == 2 and p1 == (15, 10, 7) and kl.klikniecia[1][0] > 0 and tuple(kl.poz) == (20, 10, 7),
        (kl.klikniecia, p1, kl.poz))
sprawdz("20e7 każdy klik (także udany) zostawia ślad w logu: pole, liczba pól, skąd, wynik i czas", len([l for l in logi if "marsz klikiem: klik na" in l]) == 2
        and "5 pól z (10, 10)" in logi[0] and "doszedł w" in logi[0], logi)
kl, w, pkt, logi = klik_swiat(tryb="stoi")
klikni(kl, w, pkt)
sprawdz("20e8 klik bez ruchu też ma wiersz z celem, liczbą pól i skąd", any("klik na (15, 10) 5 pól z (10, 10): nic nie ruszył" in l for l in logi), logi)
# bezpiecznik postępu po planie: plan, który po kilku polach zawraca, nie daje kliku zwiększającego drogę do końca
kl, w, pkt, logi = klik_swiat()
sprawdz("20e9 _klik_postep: cel bliżej końca planu = tak, cel za nami = nie",
        w._klik_postep(pkt, 3, (13, 10, 7), (16, 10, 7), 6) and not w._klik_postep(pkt, 3, (13, 10, 7), (11, 10, 7), 1)
        and not w._klik_postep(pkt, 3, (13, 10, 7), (13, 10, 7), 3))
kl, w, pkt, logi = klik_swiat(nad={(13, 10, 7): 1 | 4})
sprawdz("20e pole zablokowane na mapie (flaga 4): klik do pola nr 2", klikni(kl, w, pkt) is True and kl.klikniecia == [(2, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.ogien = {(14, 10)}
sprawdz("20f ogień na polu nr 4: klik skrócony do pola nr 2 (ogień też w prostokącie z marginesem)", klikni(kl, w, pkt) is True and kl.klikniecia == [(2, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.stw = [mob(14, 10, nazwa="Inny", gracz=True)]
sprawdz("20g gracz stoi na polu nr 4: klik do pola nr 3", klikni(kl, w, pkt) is True and kl.klikniecia == [(3, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.stw = [mob(14, 10, nazwa="Duch", gracz=True, widmo=True), mob(10, 10, nazwa="Ja", gracz=True)]
sprawdz("20h widmo na polu nr 4 i wpis własny postaci są pomijane: klik do pola nr 5", klikni(kl, w, pkt) is True and kl.klikniecia == [(5, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.stw = [mob(11, 12)]
sprawdz("20i mob w 3 polach od postaci: bez kliku (Cavebot zajmie się nim jak dotąd)", klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat()
kl.stw = [mob(18, 10)]
sprawdz("20i2 mob daleko: klik jak zwykle", klikni(kl, w, pkt) is True and kl.klikniecia == [(5, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.stw = [mob(16, 12)]
sprawdz("20j mob 2 pola od ścieżki (nie od postaci): klik skrócony przed nim, do pola nr 3", klikni(kl, w, pkt) is True and kl.klikniecia == [(3, 0)], kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.stw = [mob(16, 14, nazwa="Zły", gracz=True, czaszka=True)]
sprawdz("20k gracz z czaszką w widoku: bez kliku", klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat()
kl.ucieczka = True
sprawdz("20k2 trwa ucieczka: bez kliku", klikni(kl, w, pkt) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(tryb="zasieg")
r_ = klikni(kl, w, pkt)
kl.t += 1.0
r2_ = klikni(kl, w, pkt)
sprawdz("20l odrzucony klik (ValueError): bez kliku i bez wyjątku, przez 3 s nie ponawiamy co obieg", r_ is False and r2_ is False and len(kl.klikniecia) == 1, kl.klikniecia)
kl, w, pkt, logi = klik_swiat()
kl.klik = None
sprawdz("20l2 brak funkcji kliku (atak/test): bez kliku", klikni(kl, w, pkt) is False)
kl, w, pkt, logi = klik_swiat()
sprawdz("20m postać poza odcinkiem (inny rząd): bez kliku, wraca dotychczasowa maszyneria", klikni(kl, w, pkt, poz=(10, 14, 7)) is False and kl.klikniecia == [])
kl, w, pkt, logi = klik_swiat(tryb="pietro")
sprawdz("20n klik zmienia piętro: obieg zużyty (dalej _resync), wpis w logu, bez zaliczenia kliku", klikni(kl, w, pkt) is True
        and any("zmienił piętro" in l for l in logi) and w.klik_ile == 0 and kl.poz[2] == 6, (logi, kl.poz))
kl, w, pkt, logi = klik_swiat(tryb="stoi")
r1 = klikni(kl, w, pkt)
kl.t += 1.0
r2 = klikni(kl, w, pkt)
n_po = len(kl.klikniecia)
kl.t += 9.0
r3 = klikni(kl, w, pkt)
sprawdz("20o klik bez ruchu: False (wracają kroki), log, przerwa na KLIK_BLAD_PAUZA_S; po niej próba wraca",
        r1 is False and r2 is False and n_po == 1 and len(kl.klikniecia) == 2 and any("nic nie ruszył" in l for l in logi),
        (r1, r2, n_po, len(kl.klikniecia), logi))
kl, w, pkt, logi = klik_swiat()
kl.po_odczytach = (2, lambda: kl.stw.append(mob(kl.poz[0] + 2, kl.poz[1])))
r = klikni(kl, w, pkt)
sprawdz("20p mob pojawia się w trakcie marszu: przerwanie, Escape, obieg zużyty, krótka przerwa kliku",
        r is True and kl.esc == 1 and tuple(kl.poz) != (15, 10, 7) and any("przerwany" in l for l in logi)
        and w._klik_zakaz_do > kl.t, (r, kl.esc, kl.poz, logi))
kl, w, pkt, logi = klik_swiat()
kl.po_odczytach = (2, lambda: setattr(kl, "hp", 85.0))
r = klikni(kl, w, pkt)
sprawdz("20q spadek HP w trakcie marszu (o > 5 pp): przerwanie i Escape", r is True and kl.esc == 1 and tuple(kl.poz) != (15, 10, 7), (r, kl.esc, kl.poz))
kl, w, pkt, logi = klik_swiat()
kl.po_odczytach = (2, lambda: setattr(kl, "hp", 97.0))
r = klikni(kl, w, pkt)
sprawdz("20q2 mały spadek HP (3 pp) nie przerywa marszu", r is True and kl.esc == 0 and tuple(kl.poz) == (15, 10, 7), (r, kl.esc, kl.poz))

# --- integracja: ręczne „Wróć do miasta” w drodze do depo Edron (prawdziwa mapa i plan gobliny_edron) ---
def klik_integracja(konf, pre_tick=None, ruch=True):
    """Wróć-do-miasta z GOB_BLISKO: atrapa CB dostaje cb.klik, który przenosi postać na pole kliku, gdy leży ono na bieżącym odcinku."""
    s, cb, w, k, plik = wroc_swiat(poz=GOB_BLISKO, konf=konf)
    wyw = {"klik": [], "odc": 0, "fazy": set(), "etapy": []}
    stare_odc = cb._idz_odcinek

    def odc(punkty, idx):
        wyw["odc"] += 1
        return stare_odc(punkty, idx)
    cb._idz_odcinek = odc

    def klik(dx, dy):
        cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
        e = w.etapy[w.ei]
        pts = [tuple(q) for q in (e.get("punkty") or [])]
        wyw["klik"].append((tuple(s.poz), cel, pts))
        wyw["fazy"].add(w.faza)
        s.t += 0.3
        if ruch:
            s.poz[:] = list(cel)
    cb.klik = klik
    tyk(s, cb, w)
    n, wyst = bieg(s, cb, w, maks=12000, fn=pre_tick)
    return s, cb, w, k, wyw, wyst


pw20 = []
_pw.powiadom = lambda *a, **kw: pw20.append(a)
try:
    s, cb, w, k, wyw0, wyst = klik_integracja(konf_wroc())
    sprawdz("20r WYPRAWA_MARSZ_KLIK=0: dojście do depo jak dotąd, żadnego kliku, tylko kroki (bit w bit)",
            wyst and tuple(s.poz) == GOB_DEPO and wyw0["klik"] == [] and wyw0["odc"] > 5, (s.poz, len(wyw0["klik"]), wyw0["odc"]))
    s, cb, w, k, wyw1, wyst = klik_integracja(konf_wroc(WYPRAWA_MARSZ_KLIK=1))
    sprawdz("20s WYPRAWA_MARSZ_KLIK=1: dojście do depo, kliki w fazie 'do', mniej obiegów kroków niż przy 0",
            wyst and tuple(s.poz) == GOB_DEPO and len(wyw1["klik"]) >= 2 and wyw1["fazy"] == {"do"} and wyw1["odc"] < wyw0["odc"],
            (s.poz, len(wyw1["klik"]), wyw1["fazy"], wyw1["odc"], wyw0["odc"]))
    zle = []
    for z0, cel, pts in wyw1["klik"]:
        bledy_k = []
        for k_ in [i for i, q in enumerate(pts) if q[2] == z0[2] and max(abs(q[0] - z0[0]), abs(q[1] - z0[1])) <= 2]:
            pola = marsz_klik.gesta_sciezka(z0, pts[k_ + 1:])                   # gęsta ścieżka planu za punktem najbliższym postaci
            if cel[:2] not in pola:
                continue
            trasa = pola[:pola.index(cel[:2]) + 1]
            x0, x1 = min([z0[0]] + [p[0] for p in trasa]) - 1, max([z0[0]] + [p[0] for p in trasa]) + 1
            y0, y1 = min([z0[1]] + [p[1] for p in trasa]) - 1, max([z0[1]] + [p[1] for p in trasa]) + 1
            if 2 <= len(trasa) <= marsz_klik.KLIK_MAKS_POL and all(
                    marsz_klik.koszt_pola(MAPA, q[0], q[1], z0[2]) == marsz_klik.ZWYKLE for q in trasa) and not any(
                    int(MAPA.flagi(x, y, z0[2])) & 2 for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)):
                bledy_k = []
                break
            bledy_k.append((z0, cel, trasa))
        else:
            bledy_k = bledy_k or [("cel kliku poza gęstą ścieżką planu", z0, cel)]
        zle += bledy_k
    sprawdz("20t każdy klik: 2..5 pól naprzód, wszystkie pola linii zwykłe, w prostokącie z marginesem 1 zero pól z flagą 2 (schody/dziury)",
            wyw1["klik"] and not zle, zle[:2])
    sprawdz("20u po marszu klikiem nadal koniec 'depo', STOP, brak zakupów i alarmów",
            w.plik_stop.exists() and s.mowa == [] and not s.alarmy and w.zablokowany, (w.plik_stop.exists(), s.mowa, s.alarmy))
    # klik, który nic nie rusza: kroki przejmują, dojście bez utknięcia, kliki rzadkie (przerwa KLIK_BLAD_PAUZA_S)
    s, cb, w, k, wyw2, wyst = klik_integracja(konf_wroc(WYPRAWA_MARSZ_KLIK=1), ruch=False)
    sprawdz("20v klik bez ruchu: dojście do depo mimo to (kroki), kliki rzadkie, log o braku ruchu",
            wyst and tuple(s.poz) == GOB_DEPO and 0 < len(wyw2["klik"]) < 12 and any("nic nie ruszył" in l for l in w.logi),
            (s.poz, len(wyw2["klik"])))
    # mob blisko postaci: w tym czasie bez kliku (rządzi dotychczasowa logika)
    s, cb, w, k, plik = wroc_swiat(poz=GOB_BLISKO, konf=konf_wroc(WYPRAWA_MARSZ_KLIK=1))
    klik_log = []

    def klik3(dx, dy):
        klik_log.append((i3[0], tuple(s.poz)))
        cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
        s.poz[:] = list(cel)
    cb.klik = klik3
    i3 = [0]
    tyk(s, cb, w)

    def fn3(i):
        i3[0] = i
        cb.ostatnie_stwory = [mob(s.poz[0] + 1, s.poz[1], z=s.poz[2])] if i < 1 else []     # fn biegnie po skopiowaniu listy stworów w bieg()
    n, wyst = bieg(s, cb, w, maks=12000, fn=fn3)
    sprawdz("20w mob przy postaci w pierwszym obiegu: bez kliku (kroki jak dotąd), gdy mob znika, kliki wracają; dojście do depo",
            wyst and tuple(s.poz) == GOB_DEPO and not [k_ for k_ in klik_log if k_[0] < 1]
            and any(k_[0] >= 1 for k_ in klik_log), (s.poz, klik_log[:8], len(klik_log)))
    # zwykła wyprawa po zapasy (nie depo): klik tylko w fazie "do", w "z" (powrót na łowisko) kroki jak dotąd
    s, cb, w, k = nowy(jedzenie=2)
    k.WYPRAWA_MARSZ_KLIK = 1
    fazy = []

    def klik4(dx, dy):
        fazy.append(w.faza)
        s.poz[:] = [s.poz[0] + dx, s.poz[1] + dy, s.poz[2]]
    cb.klik = klik4
    pre(s, cb, w)
    n, wyst = bieg(s, cb, w, maks=9000)
    sprawdz("20x zwykła wyprawa z kliknięciami: klik wyłącznie w fazie 'do' (w 'z' i w sklepie bez), wyprawa kończy się",
            wyst and fazy and set(fazy) == {"do"}, (wyst, set(fazy), len(fazy)))
finally:
    _pw.powiadom = _stare

# --- WROC_REFILL: decyzja przy STOP w depo (czekacz podmieniony; prawdziwy refill.sh/serwis nie biegną) ---
def refill_bieg(konf, poz=GOB_BLISKO, przed=None, procesy=None, start=None, plan=None, domysl_start=True):
    s, cb, w, k, plik = wroc_swiat(poz=poz, konf=konf, plan=plan)
    (w.plik_stop.parent / refill_auto.PLIK).unlink(missing_ok=True)       # katalog TMP jest wspólny dla prób: czysta decyzja
    starty = []
    w.refill_start = start or (lambda: starty.append(1))
    w.refill_procesy = procesy or (lambda wzor, **kw: [])
    if przed:
        przed(s, cb, w)
    pw20.clear()
    tyk(s, cb, w)
    n, wyst = bieg(s, cb, w, maks=12000)
    stan = refill_auto.czytaj_stan(w.plik_stop.parent)
    return s, cb, w, starty, stan, wyst


pw20.clear()
_pw.powiadom = lambda *a, **kw: pw20.append(a)
try:
    s, cb, w, st, stan, wyst = refill_bieg(konf_wroc())
    sprawdz("20y WROC_REFILL=0 (domyślnie): bot staje w depo jak dotąd, czekacz nie rusza, brak pliku decyzji, komunikat 'potrzebny człowiek'",
            wyst and tuple(s.poz) == GOB_DEPO and w.plik_stop.exists() and st == [] and stan == {}
            and any(a[0] == "Wyprawa: jestem w depo" and "potrzebny człowiek" in a[1] and "refill" not in a[1] for a in pw20), (st, stan, pw20))
    w.plik_stop.unlink()
    s, cb, w, st, stan, wyst = refill_bieg(konf_wroc(WROC_REFILL=1))
    sprawdz("20z WROC_REFILL=1, depo Edron: STOP zapisany, czekacz uruchomiony RAZ, decyzja 'czeka', komunikat 'refill startuje sam'",
            wyst and tuple(s.poz) == GOB_DEPO and w.plik_stop.exists() and st == [1] and stan.get("stan") == "czeka"
            and any(a[0] == "Wyprawa: jestem w depo" and "refill startuje sam" in a[1] for a in pw20), (st, stan, pw20))
    for _ in range(40):                        # dalsze ticki po dojściu nie uruchamiają drugiego czekacza
        tyk(s, cb, w, 5.0)
        w.tick()
    sprawdz("20z2 po dojściu czekacz nie rusza drugi raz (wyprawa zablokowana, zlecenie zużyte)", st == [1] and w.zablokowany, st)
    w.plik_stop.unlink()

    def stop_reczny(s, cb, w):
        w.plik_stop.with_name("STOP_RECZNY").write_text("")
    s, cb, w, st, stan, wyst = refill_bieg(konf_wroc(WROC_REFILL=1), przed=stop_reczny)
    sprawdz("20za STOP_RECZNY: ręczny stop ma pierwszeństwo, czekacz nie rusza, powód w pliku decyzji, bot i tak stoi w depo",
            wyst and st == [] and stan.get("stan") == "pominiety" and "ręczny" in stan.get("powod", "") and w.plik_stop.exists(), (st, stan))
    w.plik_stop.with_name("STOP_RECZNY").unlink()
    w.plik_stop.unlink()
    s, cb, w, st, stan, wyst = refill_bieg(konf_wroc(WROC_REFILL=1),
                                           procesy=lambda wzor, **kw: [4242] if "serwis" in wzor else [])
    sprawdz("20zb serwis już działa: czekacz nie rusza, decyzja 'pominiety: serwis już trwa'",
            wyst and st == [] and stan.get("stan") == "pominiety" and "serwis" in stan.get("powod", ""), (st, stan))
    w.plik_stop.unlink()
    s, cb, w, st, stan, wyst = refill_bieg(konf_wroc(WROC_REFILL=1), start=lambda: (_ for _ in ()).throw(OSError("brak bash")))
    sprawdz("20zc czekacz nie wystartował: wyjątek nie psuje zatrzymania w depo, decyzja 'pominiety', STOP jest",
            wyst and stan.get("stan") == "pominiety" and "nie udało się" in stan.get("powod", "") and w.plik_stop.exists()
            and tuple(s.poz) == GOB_DEPO, stan)
    w.plik_stop.unlink()
    # Thais (plan troll z jaskini trolli): od 22.10 ma plan serwisu (drzwi sklepów przechodzi serwis), więc auto-refill rusza jak w Edronie;
    # trasa i atrapa jak w 12. (Wcześniej: brak_planu, dymek „bez auto-refillu”.)
    s, cb, w, k, plik = wroc_swiat(poz=START, konf=konf_wroc(WROC_REFILL=1))
    (w.plik_stop.parent / refill_auto.PLIK).unlink(missing_ok=True)
    st = []
    w.refill_start = lambda: st.append(1)
    w.refill_procesy = lambda wzor, **kw: []
    pw20.clear()
    tyk(s, cb, w)
    n, wyst = bieg(s, cb, w, maks=12000)
    stan = refill_auto.czytaj_stan(w.plik_stop.parent)
    sprawdz("20zd Thais (plan 'troll', depo Thais): serwis Thais ma plan = auto-refill rusza RAZ (czekacz), decyzja 'czeka', STOP w depo, bez wpisu o braku planu",
            wyst and tuple(s.poz) == DEPO and st == [1] and stan.get("stan") == "czeka" and "thais" in stan.get("powod", "")
            and w.plik_stop.exists() and not any("auto-refill pominięty" in l for l in w.logi)
            and not any(a[0] == "Wróć do miasta: bez auto-refillu" for a in pw20), (s.poz, st, stan, pw20))
    w.plik_stop.unlink()
    # nieudane dojście (blokada marszu): alarm + STOP bez auto-refillu
    s, cb, w, k, plik = wroc_swiat(poz=GOB_BLISKO, konf=konf_wroc(WROC_REFILL=1))
    (w.plik_stop.parent / refill_auto.PLIK).unlink(missing_ok=True)
    st = []
    w.refill_start = lambda: st.append(1)
    tyk(s, cb, w)
    s.blokada_marszu = True
    n, wyst = bieg(s, cb, w, maks=12000)
    sprawdz("20ze dojście nie udało się (utknięcie): alarm i STOP jak dotąd, auto-refill NIE rusza", st == [] and w.plik_stop.exists()
            and refill_auto.czytaj_stan(w.plik_stop.parent) == {}, (st, wyst, w.plik_stop.exists(), refill_auto.czytaj_stan(w.plik_stop.parent), w.logi[-3:]))
    w.plik_stop.unlink()
finally:
    _pw.powiadom = _stare

okr, blr = pokretla.waliduj({"WYPRAWA_MARSZ_KLIK": 1, "WROC_REFILL": 1}, {"WYPRAWA_MARSZ_KLIK": 0, "WROC_REFILL": 0})
ok1, bl1 = pokretla.waliduj({"WYPRAWA_MARSZ_KLIK": 1, "WROC_REFILL": 1})
sprawdz("20zf pokrętła: cavebot ma stałe = 0, na_zywo.json je przyjmuje (0/1), analityk nie włączy",
        cavebot.WYPRAWA_MARSZ_KLIK == 0 and cavebot.WROC_REFILL == 0 and ok1 == {"WYPRAWA_MARSZ_KLIK": 1, "WROC_REFILL": 1}
        and not okr and len(blr) == 2, (ok1, okr, blr))

if _os.environ.get("DBG"):
    print(DBGLOG)
print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
