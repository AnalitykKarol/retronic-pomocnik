"""Wpadnięcie w pościgu (20.10, SPEC_orbity_straznik_1020 A; przypadek K1: Kutangen, Rook, 16:38:18-27).
Klient, prowadzony klikiem ataku, wchodzi w dziurę (32086,32197,8) w trakcie pościgu za Rat (HP 20%, odl 7) z (32078,32201,8);
pościg trwa kilka s bez obiegu ticka, więc ostatnia próbka `obserwuj` była 8 pól dalej i `_cheb > WPADNIECIE_ODL` gubiło wykrycie.
Testy: pokrętło WPADNIECIE_POSCIG=1 -> "Wpadłem", nauka dziury, stan wyjścia; =0 -> brak wykrycia jak dotąd;
teleport > 15 pól w pościgu nadal nie jest wpadnięciem. Atrapy + PRAWDZIWA mapa serwera (mapa.py)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie, powiadom
from pathlib import Path

LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.DZIURA_PRZY_CELU = 0         # K1 wydarzył się bez tej ochrony (cel przy dziurze nie jest odpuszczany)
cavebot.POSCIG_OKNO = 9.0; cavebot.POSCIG_OKNO_DOBRY = 9.0        # K1: pościg trwał 9 s bez obiegu ticka
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
powiadom.powiadom = lambda *a, **k: None
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
START = (32078, 32201, 8)
DZIURA = (32086, 32197, 8)           # pole z flagą 2 na z8 (log 20.10 16:38:27)
LAD = (32086, 32197, 9)
sprawdz("0 mapa: dziura (32086,32197,8) ma flagę 2, lądowanie na z9 chodliwe",
        M.flagi(*DZIURA) & 2 and not M.flagi(*DZIURA) & 4 and M.flagi(*LAD) & 1 and not M.flagi(*LAD) & 4,
        f"{M.flagi(*DZIURA)} {M.flagi(*LAD)}")

# droga klienta: korytarz y=32201 na wschód do x=32085, na północ do y=32198, skos w dziurę
SCIEZKA = [(x, 32201, 8) for x in range(32079, 32086)] + [(32085, y, 8) for y in (32200, 32199, 32198)] + [DZIURA[:2] + (8,)]
SCIEZKA_DZIURA = SCIEZKA[:-1] + [LAD]          # wejście w dziurę = od razu z9
SZCZUR = {"id": 77, "nazwa": "Rat", "gracz": False, "x": 32085, "y": 32197, "z": 8, "hp": 20, "adres": "0x1000"}


class Swiat:
    """Gracz porusza się sam po zadanej drodze (klient prowadzony klikiem ataku), 0,55 s na pole; klawisze bota nic nie zmieniają."""
    def __init__(s, sciezka):
        s.t = 0.0; s.poz = list(START); s.sciezka = list(sciezka); s.nast = 0.5; s.zmiany = []
        s.stwory = [dict(SZCZUR)]; s.klawisze = []; s.uzycia = []; s.liny = []
    def zegar(s): return s.t
    def _adv(s):
        if s.t > 4.0 and s.stwory: s.stwory[0]["x"], s.stwory[0]["y"] = 32087, 32196        # szczur ucieka dalej, żeby nie być obok przy dziurze
        while s.sciezka and s.t >= s.nast:
            n = s.sciezka.pop(0); s.nast += 0.55
            if n[2] != s.poz[2]: s.zmiany.append((tuple(s.poz), n))
            s.poz[:] = list(n)
    def spij(s, d): s.t += d; s._adv()
    def zapytaj(s, z):
        s.t += 0.02; s._adv()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0, "proc": 100.0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        if z["cmd"] in ("poscig", "stwor"):
            m = s.stwory[0]
            odp = {"id": m["id"], "x": m["x"], "y": m["y"], "z": m["z"], "hp": m["hp"], "atakowany": True, "bije_nas": False}
            if z["cmd"] == "stwor": return {"stwor": odp}
            return {"pozycja": {"x": s.poz[0], "y": s.poz[1], "z": s.poz[2]}, "stwor": odp}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): p.s._adv(); return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k): p.s.klawisze.append(k); return False


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzycia.append(tuple(pole))
    def uzyj_line(o, pole, poz): o.s.liny.append(tuple(pole))


def nowy(sciezka, poscig, dziury=()):
    LOG.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    cavebot.WPADNIECIE_POSCIG = poscig
    s = Swiat(sciezka)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    trasa = [(32075, 32201, 8), (32079, 32201, 8)]
    b = cavebot.Cavebot(P(s), trasa, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=lambda dx, dy: None)
    b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        kopia = kat / "na_zywo.json"; kopia.write_text("{}"); b.pokretla.plik = kopia
    w = b._wp(); w.plik_stop = kat / "STOP"
    return s, b


def bieg(s, b, n=6):
    for _ in range(n):
        if not b.tick(): break


# --- K1, pokrętło 1 ---
s, b = nowy(SCIEZKA_DZIURA, 1)
b.tick()
sprawdz("1a jeden tick (pościg) trwał kilka s bez obiegu i skończył na z9", s.poz[2] == 9 and s.t > 4.0, f"t={s.t:.1f} poz={s.poz}")
sprawdz("1b ostatnia próbka obserwuj to pole z8 tuż przed dziurą, nie sprzed pościgu",
        b.wpadniecie._ost is not None and b.wpadniecie._ost[0][2] == 8 and b.wpadniecie._ost[0][:2] == (32085, 32198),
        b.wpadniecie._ost)
bieg(s, b, 4)
tekst = "\n".join(LOG)
sprawdz("1c log \"Wpadłem\" z polem z8 tuż przed dziurą i lądowaniem", "Wpadłem: (32085,32198,8) -> (32086,32197,9)" in tekst)
sprawdz("1d nauka dziury (32086,32197,8), zapisana do pliku", DZIURA in b.wpadniecie.dziury and wpadniecie.PLIK_DZIUR.exists())
st = b.wpadniecie.st
sprawdz("1e stan wyjścia: wpadnięcie w toku z z8 <- z9, stan WPADNIECIE",
        st is not None and st["z0"] == 8 and st["z1"] == 9 and str(b.stan).startswith("WPADNIECIE"), (st and (st["z0"], st["z1"]), b.stan))
sprawdz("1f jedno wykrycie", b.wpadniecie.wykryte == 1, b.wpadniecie.wykryte)

# --- K1, pokrętło 0: jak dotąd (brak wykrycia) ---
s, b = nowy(SCIEZKA_DZIURA, 0)
b.tick(); bieg(s, b, 4)
tekst = "\n".join(LOG)
sprawdz("2a pokrętło 0: pościg doszedł do z9 tak samo", s.poz[2] == 9 and s.t > 4.0, f"t={s.t:.1f} poz={s.poz}")
sprawdz("2b pokrętło 0: brak wykrycia, brak nauki dziury, brak stanu wyjścia",
        "Wpadłem" not in tekst and not b.wpadniecie.dziury and b.wpadniecie.st is None and b.wpadniecie.wykryte == 0,
        tekst[-400:])
sprawdz("2c pokrętło 0: próbka obserwuj nie jest odświeżana w pętli (z8 sprzed pościgu albo z9 z ticka)",
        b.wpadniecie._ost[0] != (32085, 32198, 8), b.wpadniecie._ost)

# --- teleport (> 15 pól) w trakcie pościgu: nie jest wpadnięciem ---
TELE = SCIEZKA[:-1] + [(32100, 32230, 9)]
s, b = nowy(TELE, 1)
b.tick(); bieg(s, b, 4)
tekst = "\n".join(LOG)
sprawdz("3 teleport > 15 pól w pościgu (z8 -> z9 daleko) nie jest wpadnięciem",
        s.poz[2] == 9 and "Wpadłem" not in tekst and not b.wpadniecie.dziury and b.wpadniecie.wykryte == 0, tekst[-400:])

# --- zmiana piętra o planowane przejście i brak pościgu: bez zmian (zwykły upadek między tickami nadal działa przy 1) ---
s, b = nowy([DZIURA[:2] + (9,)], 1)
s.poz[:] = [32085, 32198, 8]; s.stwory.clear()
b.tick(); bieg(s, b, 3)
sprawdz("4 zwykły upadek między tickami (bez pościgu) nadal wykrywany przy pokrętle 1", b.wpadniecie.wykryte == 1 and DZIURA in b.wpadniecie.dziury,
        "\n".join(LOG)[-300:])

print("\nWSZYSTKO OK" if all(ok) else "\nSĄ BŁĘDY")
sys.exit(0 if all(ok) else 1)
