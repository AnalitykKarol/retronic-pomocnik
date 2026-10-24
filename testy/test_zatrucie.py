#!/usr/bin/env python3
"""23.10 zgon odchyda/gebelisha pod dziurą (32354,32131,z8), Scorpion („okropna trucizna”): bot nie wykrywał zatrucia i nie leczył go.
Sprawdza: (1) zatrucie.Zatrucie na ciągach HP (trucizna: tyknięcia 1-3 HP co ~2,5 s; nie wywołuje: cios w zwarciu, ogień, leczenie),
(2) odczyt z pola `stany` (bitmaska z pamięci, gdy będzie zmierzona), (3) Cavebot: exana pox gdy klawisz i mana, inaczej antidote rune (3153) na siebie,
przerwa po próbie, 3 porażki = przerwa 5 min, (4) zatrucie + kieszeń na złym piętrze: bez UCIECZKI, leczenie exurą działa, wyjście (Use/lina) nie jest blokowane.
Ciągi HP są syntetyczne (bez pomiaru na żywo: m_states niezmierzony); atrapy, bez gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import mapa as _mapa
import powiadom
import wpadniecie
import zatrucie
import wypad

LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
powiadom.powiadom = lambda *a, **k: None
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


sprawdz("0 id antidote rune w danych bota = 3153", zatrucie.ID_ANTIDOTE_RUNE == 3153 and wypad.ID_ANTIDOTE == 3153)
import json
_prz = json.load(open(Path(__file__).resolve().parent.parent / "dane_tibia" / "przedmioty.json"))
_ls = [x for k in _prz["kategorie"] for x in (_prz["kategorie"][k] if isinstance(_prz["kategorie"], dict) else k.get("przedmioty", []))] if isinstance(_prz.get("kategorie"), (dict, list)) else []
_ant = [x for x in _ls if isinstance(x, dict) and x.get("nazwa") == "antidote rune"]
sprawdz("0b dane_tibia/przedmioty.json: antidote rune id_klienta 3153", _ant and _ant[0].get("id_klienta") == 3153, _ant)


def przebieg(hps, krok=2.5, **kw):
    z = zatrucie.Zatrucie(); t = 100.0; wyn = []
    for hp in hps:
        t += krok; wyn.append(z.odczyt(t, hp, **kw))
    return wyn


# --- 1. detektor z HP ---
trucizna = [150, 149, 147, 146, 144, 143, 141]
sprawdz("1a trucizna 1-3 HP co 2,5 s bez stwora -> wykryta", przebieg(trucizna)[-1] is True, przebieg(trucizna))
sprawdz("1b dwa tyknięcia to jeszcze za mało", przebieg(trucizna[:3])[-1] is False)
sprawdz("1c to samo, ale stwór obok -> NIE zatrucie (cios w zwarciu)", not any(przebieg(trucizna, stwor_obok=True)))
sprawdz("1d to samo na polu ognia -> NIE zatrucie", not any(przebieg(trucizna, ogien=True)))
sprawdz("1e duże ciosy (10 HP) bez stwora (strzał z dystansu) -> NIE zatrucie", not any(przebieg([150, 140, 130, 120, 110])))
sprawdz("1f leczenie w środku zeruje okno", przebieg([150, 149, 147, 170, 169, 168])[-1] is False)
sprawdz("1g stałe HP -> brak", not any(przebieg([150] * 8)))
sprawdz("1h pole stany z pamięci: bit 1 -> zatrucie, 0 -> brak (niezależnie od HP)",
        zatrucie.Zatrucie().odczyt(1.0, 150, stany=1) and not zatrucie.Zatrucie().odczyt(1.0, 100, stany=0))
z = zatrucie.Zatrucie()
sprawdz("1i po_probie: 3 porażki z rzędu = przerwa 5 min", (z.po_probie(10, True), z.po_probie(20, True), z.po_probie(30, True), z.po_probie(40, True),
        not z.gotowy(100) and z.gotowy(40 + 301))[-1], (z.porazki, z.do))


# --- 2. Cavebot ---
M = _mapa.Mapa()
DZIURA = (32354, 32131, 8); SPOT = (32354, 32131, 9); KIESZEN = (32354, 32132, 9); Z8 = (32355, 32131, 8)


class Swiat:
    def __init__(s, hp=150, mana=34, poz=Z8, stany=None):
        s.t = 0.0; s.poz = list(poz); s.hp = hp; s.mana = mana; s.stany = stany
        s.klawisze = []; s.liny = []; s.uzyte = []; s.antidote = []; s.stwory = []

    def zegar(s): return s.t
    def spij(s, d): s.t += d

    def zapytaj(s, z):
        s.t += 0.02
        if z["cmd"] == "gracz":
            g = {"hp": s.hp, "max_hp": 185, "mana": s.mana, "max_mana": 35, "proc": 100.0 * s.hp / 185}
            if s.stany is not None:
                g["stany"] = s.stany
            return {"gracz": g}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}] + s.stwory}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k): p.s.klawisze.append(k); return False


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzyte.append((tuple(pole), tuple(poz)))
    def uzyj_line(o, pole, poz): o.s.liny.append(tuple(pole))
    def uzyj_antidote(o, poz): o.s.antidote.append(tuple(poz))


def nowy(s, klawisz="", runa=1, zdrowie=0):
    LOG.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    cavebot.ZATRUCIE_AKTYWNY = 1; cavebot.ZATRUCIE_CZAR_KLAWISZ = klawisz; cavebot.ZATRUCIE_RUNA = runa; cavebot.ZATRUCIE_CZAR_KOSZT = 30
    cavebot.ZDROWIE_CZAR_AKTYWNY = zdrowie; cavebot.WPADNIECIE_UCIECZKA = 1; cavebot.WPADNIECIE_BIJ = 1; cavebot.WPADNIECIE_DRABINA = 1
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    trasa = [(32355, 32135, 8), (32355, 32139, 8), (32356, 32139, 8)]
    b = cavebot.Cavebot(P(s), trasa, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, mapa=M, potwory=["troll", "rat"])
    b.przerwa_od = float("inf"); b.prog_aktualny = 45.0; b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        kopia = kat / "na_zywo.json"; kopia.write_text("{}"); b.pokretla.plik = kopia
    b._wp().plik_stop = kat / "STOP"
    b.idx = 2
    return b


def trucij(s, b, hps, krok=2.5):
    for hp in hps:
        s.hp = hp; s.t += krok
        b.tick()


# 2a: klawisz exana pox + mana -> czar, bez runy
s = Swiat(); b = nowy(s, klawisz="F5")
trucij(s, b, trucizna)
sprawdz("2a exana pox [F5] wciśnięty, runa nieużyta", "F5" in s.klawisze and not s.antidote, (s.klawisze, s.antidote, LOG[-3:]))
sprawdz("2a2 bot wie, że jest zatruty", b.zatruty is True)
# 2b: brak klawisza -> antidote rune na siebie
s = Swiat(); b = nowy(s, klawisz="")
trucij(s, b, trucizna)
sprawdz("2b brak klawisza: antidote rune na własne pole", s.antidote and s.antidote[0] == tuple(s.poz), (s.antidote, LOG[-3:]))
# 2c: za mało many na czar -> runa
s = Swiat(mana=10); b = nowy(s, klawisz="F5")
trucij(s, b, trucizna)
sprawdz("2c mana 10 < 30: zamiast czaru runa", "F5" not in s.klawisze and s.antidote, (s.klawisze, s.antidote))
# 2d: ZATRUCIE_RUNA=0, brak klawisza -> nic
s = Swiat(); b = nowy(s, klawisz="", runa=0)
trucij(s, b, trucizna)
sprawdz("2d bez klawisza i bez runy: nic nie robi, nie wywraca bota", not s.antidote and "F5" not in s.klawisze)
# 2e: przerwa po próbie (PRZERWA_S): w 3 s po próbie nie ponawia
s = Swiat(); b = nowy(s, klawisz="")
trucij(s, b, trucizna)
n = len(s.antidote)
trucij(s, b, [139, 138], krok=1.0)
sprawdz("2e przerwa po próbie: bez ponowienia w ciągu 2 s", len(s.antidote) == n, (n, len(s.antidote)))
# 2f: stwór obok (zwarcie) -> nie leczy zatrucia z HP
s = Swiat(); s.stwory = [{"id": 5, "nazwa": "Troll", "gracz": False, "x": Z8[0] + 1, "y": Z8[1], "z": 8, "hp": 100}]
b = nowy(s, klawisz="")
trucij(s, b, trucizna)
sprawdz("2f stwór obok: ciągły ubytek HP to walka, nie trucizna", not s.antidote, s.antidote)
# 2g: pole stany z pamięci
s = Swiat(stany=1); b = nowy(s, klawisz="F5")
b.tick()
sprawdz("2g stany=1 z pamięci: od razu exana pox (bez czekania na ciąg HP)", "F5" in s.klawisze, (s.klawisze, LOG[-3:]))
s = Swiat(stany=0); b = nowy(s, klawisz="F5")
trucij(s, b, trucizna)
sprawdz("2g2 stany=0 z pamięci: ciąg HP ignorowany", "F5" not in s.klawisze and not s.antidote)
# 2h: ZATRUCIE_AKTYWNY=0 wyłącza
s = Swiat(); b = nowy(s, klawisz="F5"); cavebot.ZATRUCIE_AKTYWNY = 0
trucij(s, b, trucizna)
sprawdz("2h ZATRUCIE_AKTYWNY=0: nic", "F5" not in s.klawisze and not s.antidote)

# --- 3. zatrucie + zły piętro (kieszeń z9): bez UCIECZKI, leczenie, wyjście nie blokowane ---
s = Swiat(hp=150, mana=34, poz=Z8, stany=1); b = nowy(s, klawisz="F5", zdrowie=1)   # zatrucie z pamięci (deterministycznie); wykrycie z HP: sekcja 2
b.tick()
s.poz[:] = list(SPOT); b.tick(); s.poz[:] = list(KIESZEN)
st = b.wpadniecie.st
st["lina"] = 0; st["uzyj"] = 0; st["lina_zszedl"] = True; st["nast"] = 0.0
s.klawisze.clear(); s.liny.clear(); s.uzyte.clear(); s.antidote.clear()
s.hp = 70                                            # 38% <= próg UCIECZKI (45%), zatruty, w kieszeni
for _ in range(60):
    s.t += 0.5
    b.tick()
sprawdz("3a zatruty w kieszeni: exana pox i exura (F2)", "F5" in s.klawisze and "F2" in s.klawisze, (s.klawisze, LOG[-4:]))
sprawdz("3b zatruty w kieszeni: bez kroków UCIECZKI w stronę trasy z innego piętra", not any(k in ("Down", "Right", "Left", "Up") for k in s.klawisze), s.klawisze)
sprawdz("3c leczenie nie głodzi wyjścia: lina i Use próbowane mimo trucizny i exury co obieg", s.liny and s.uzyte, (s.liny, s.uzyte, LOG[-5:]))
sprawdz("3d stan nie jest UCIECZKA", "UCIECZKA" not in str(b.stan), b.stan)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
