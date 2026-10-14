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
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1))
sprawdz("15b tryb depo, blanki 0, zapas ok, WYPRAWA_DEPO_BLANKI=0: brak wyprawy", not pre(s, cb, w, 6) and not cb.wypad_aktywny)
sprawdz("15b2 jednorazowa notatka o braku blanków", sum("brak blanków" in l for l in w.logi) == 1, w.logi[-3:])
s, cb, w, k = nowy(jedzenie=5, torch=5, konf=konf_depo(WYPRAWA_BLANKI=10, WYPRAWA_BLANKI_PROG=1, WYPRAWA_DEPO_BLANKI=1))
sprawdz("15c WYPRAWA_DEPO_BLANKI=1: wyprawa 'depo:blanki' startuje", pre(s, cb, w, 6) and w.powod.startswith("wyprawa:depo:blanki"), w.powod)
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

if _os.environ.get("DBG"):
    print(DBGLOG)
print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
