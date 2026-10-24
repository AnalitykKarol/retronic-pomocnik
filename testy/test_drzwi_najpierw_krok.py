"""Drzwi: NAJPIERW krok, Use dopiero gdy krok nie ruszył postaci (24.10, Karol: „sam je zamyka, próbuje, otwiera i przechodzi”).
Odchyd 24.10 11:34:31, drzwi (32657,31965,z8) na trasie: Use 1/3 i 2/3 na drzwiach, które stały OTWARTE (Use na otwartych je zamyka):
pierwszy krok w epizodzie został zgubiony, potem tylko Use + krok. Poprawka: cavebot.DRZWI_NAJPIERW_KROK (przed każdym Use krok,
po stojącej pozycji drugi krok, po Use znowu krok; _drzwi_trasa_tick i _drzwi_hak). Pokrętło 0 = stare zachowanie.
Atrapy z test_drzwi_trasa.py (prawdziwa mapa i trasy), model drzwi: Use PRZEŁĄCZA (otwarte <-> zamknięte). Bez gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_drzwi_trasa.py").read_text()
_src = _src[:_src.index("# --- 1. wykrywanie drzwi na trasie ---")]
_g2 = {"__file__": str(KAT / "testy" / "test_drzwi_trasa.py"), "__name__": "atrapy_drzwi_trasa"}
exec(compile(_src, "test_drzwi_trasa(atrapy)", "exec"), _g2)
globals().update({k: v for k, v in _g2.items() if not k.startswith("__")})
ok.clear()

HAS = hasattr(cavebot, "DRZWI_NAJPIERW_KROK")


class P4(P3):
    """Krok może być zgubiony: `zgub` = ile najbliższych wywołań krok() nie rusza postaci (klient gubi klawisz w animacji)."""
    def krok(p, k):
        s = p.s
        s.kroki.append((round(s.t, 2), k, tuple(s.poz), STAN["otwarte"], len(s.uzycia)))
        if s.zgub > 0 and (s.zgub_na is None or tuple(s.poz) == s.zgub_na):
            s.zgub -= 1
            s.t += 0.2
            return False
        if s.zgub_po_uzyciu and s.uzycia and not s.zgub_po_uzyciu_zrobione and len(s.uzycia) > s.kroki_przed_uzyciem:
            s.zgub_po_uzyciu_zrobione = True
            s.t += 0.2
            return False
        return P3.krok(p, k)


class Swiat4(Swiat3):
    """Use PRZEŁĄCZA drzwi (jak w OTS: otwarte -> zamknięte, zamknięte -> otwarte)."""
    def __init__(s, poz, zgub=0, zgub_po_uzyciu=False, **kw):
        super().__init__(poz, **kw)
        s.zgub = zgub
        s.zgub_na = None          # pole, na którym kroki są gubione (None = gdziekolwiek); trasa: tylko przed drzwiami, nie w podejściu
        s.zgub_po_uzyciu = zgub_po_uzyciu
        s.zgub_po_uzyciu_zrobione = False
        s.kroki_przed_uzyciem = 0
        s.kroki = []

    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        s.uz_poz.append(tuple(s.poz))
        if s.model_animacji and s.t - s.ostatni_ruch < KROK_ANIM_S:
            s.zgubione += 1
            return
        if tuple(pole) in (DR, EDRON) and s.drzwi_dzialaja:
            STAN["otwarte"] = not STAN["otwarte"]


def zrob4(s, punkty, fabryka=None, **kw):
    b = zrob3(s, punkty, fabryka=fabryka, **kw)
    b.postac = P4(s)
    return b


def dojscie4(otwarte, zgub=0, zgub_po_uzyciu=False, drzwi_dzialaja=True, maks=1500, limit_s=60.0):
    LOG.clear()
    s = Swiat4(START_D, zgub=zgub, zgub_po_uzyciu=zgub_po_uzyciu, drzwi_dzialaja=drzwi_dzialaja)
    s.zgub_na = (33166, 31816, 7)
    STAN["otwarte"] = otwarte
    b = zrob4(s, list(DOJ_Z7))
    n = 0
    while n < maks and s.t < limit_s and b.tick():
        n += 1
        s.t += 0.05
    return s, b, n


def dosz(s):
    return s.poz[1] >= 31820


cavebot.DRZWI_TRASA = 1
cavebot.DRZWI_SPOKOJ = 1
if HAS:
    cavebot.DRZWI_NAJPIERW_KROK = 1

# --- 1. trasa: drzwi OTWARTE ---
s, b, n = dojscie4(otwarte=True)
sprawdz("1a otwarte, krok działa: przejście bez Use", dosz(s) and not s.uzycia, f"poz={s.poz} uz={s.uzycia}")

s, b, n = dojscie4(otwarte=True, zgub=1)
sprawdz("1b otwarte, pierwszy krok zgubiony (odchyd 11:34:31): przejście bez Use, drzwi zostają otwarte",
        dosz(s) and not s.uzycia and STAN["otwarte"], f"poz={s.poz} uz={s.uzycia} otw={STAN['otwarte']} kroki={s.kroki[:4]}")

s, b, n = dojscie4(otwarte=True, zgub=2)
sprawdz("1c otwarte, dwa kroki zgubione z rzędu: Use dopiero po nich (1 Use zamyka, 2. otwiera, przejście) - nic poniżej progu",
        dosz(s) and len(s.uzycia) <= 2, f"poz={s.poz} uz={s.uzycia}")

# --- 2. trasa: drzwi ZAMKNIĘTE ---
s, b, n = dojscie4(otwarte=False)
przed_use = [k for k in s.kroki if k[4] == 0 and k[2][1] == 31816]
sprawdz("2a zamknięte: krok nie rusza, potem jeden Use i przejście", dosz(s) and len(s.uzycia) == 1 and STAN["otwarte"], f"poz={s.poz} uz={s.uzycia}")
sprawdz("2b zamknięte: przed pierwszym Use co najmniej 2 próby kroku (krok, stanie, krok)", len(przed_use) >= 2, f"{przed_use}")
sprawdz("2c Use tylko z pola przed drzwiami, żaden Use zgubiony", set(s.uz_poz) == {(33166, 31816, 7)} and s.zgubione == 0, f"{s.uz_poz} zgubione={s.zgubione}")

# Use otworzył, ale krok zaraz po Use zgubiony: następny obieg zaczyna się krokiem, NIE drugim Use (drugi zamknąłby drzwi)
s = Swiat4(START_D, zgub_po_uzyciu=True)
LOG.clear()
STAN["otwarte"] = False
b = zrob4(s, list(DOJ_Z7))
n = 0
while n < 1500 and s.t < 60 and b.tick():
    n += 1
    s.t += 0.05
sprawdz("2d Use otworzył, krok po Use zgubiony: kolejny obieg krokiem, nie drugim Use", dosz(s) and len(s.uzycia) == 1 and STAN["otwarte"],
        f"poz={s.poz} uz={s.uzycia} otw={STAN['otwarte']}")

s, b, n = dojscie4(otwarte=False, drzwi_dzialaja=False)
sprawdz("2e drzwi niedziałające: max DRZWI_TRASA_PROB Use i jedna notatka o odpuszczeniu",
        1 <= len(s.uzycia) <= cavebot.DRZWI_TRASA_PROB and sum("odpuszczam" in l for l in LOG) == 1, f"uz={len(s.uzycia)} {[l for l in LOG if 'odpuszczam' in l]}")

# --- 3. pokrętło 0 = stare zachowanie ---
if HAS:
    cavebot.DRZWI_NAJPIERW_KROK = 0
    s, b, n = dojscie4(otwarte=True, zgub=1)
    sprawdz("3a pokrętło 0: pierwszy krok zgubiony na OTWARTYCH drzwiach = Use (zamyka), potem 2. Use i przejście (jak 11:34:31)",
            len(s.uzycia) >= 2 and dosz(s), f"poz={s.poz} uz={s.uzycia}")
    s, b, n = dojscie4(otwarte=False)
    sprawdz("3b pokrętło 0: zamknięte drzwi nadal otwierane (1 Use, przejście)", dosz(s) and len(s.uzycia) == 1, f"poz={s.poz} uz={s.uzycia}")
    cavebot.DRZWI_NAJPIERW_KROK = 1
else:
    sprawdz("3 pokrętło DRZWI_NAJPIERW_KROK istnieje", False, "brak w cavebot")

# --- 4. _drzwi_hak (drzwi jaskini z PLIK_DRZWI, patrol/pościg) ---
def hak(otwarte, zgub=0, zgub_po_uzyciu=False, drzwi_dzialaja=True, obiegi=6):
    """Postać stoi obok drzwi (32504 -> drzwi 32505), epizod stary (> DRZWI_KROK_S): hak decyduje o Use. Zwraca (świat, bot, wyniki haka)."""
    cavebot.PATROL_DRZWI = 1
    LOG.clear()
    s = Swiat4((32504, 32270, 8), zgub=zgub, zgub_po_uzyciu=zgub_po_uzyciu, drzwi_dzialaja=drzwi_dzialaja)
    STAN["otwarte"] = otwarte
    b = zrob4(s, list(troll), fabryka=cavebot.Cavebot)
    b.drzwi_stan[DR] = {"poz": (32504, 32270, 8), "t0": s.t, "proby": 0, "zle_do": float("-inf"), "nota": False, "otw": False}
    s.t += cavebot.DRZWI_KROK_S + 0.2
    wyn = []
    kolej = [DR, (32506, 32270, 8)]
    for _ in range(obiegi):
        poz = tuple(s.poz)
        if poz[0] >= 32505:
            break
        w = b._drzwi_hak(poz, kolej, False)
        wyn.append(w)
        s.t += 0.25
    return s, b, wyn


pd0 = cavebot.PATROL_DRZWI
s, b, w = hak(otwarte=True)
sprawdz("4a hak, drzwi otwarte: krok przez drzwi, bez Use", s.poz[0] >= 32505 and not s.uzycia, f"poz={s.poz} uz={s.uzycia} w={w}")
s, b, w = hak(otwarte=True, zgub=1)
sprawdz("4b hak, drzwi otwarte, pierwszy krok zgubiony: bez Use, przejście", s.poz[0] >= 32505 and not s.uzycia and STAN["otwarte"], f"poz={s.poz} uz={s.uzycia} w={w}")
s, b, w = hak(otwarte=False)
sprawdz("4c hak, drzwi zamknięte: jeden Use i krok przez drzwi", s.poz[0] >= 32505 and len(s.uzycia) == 1 and STAN["otwarte"], f"poz={s.poz} uz={s.uzycia} w={w}")
s, b, w = hak(otwarte=False, zgub_po_uzyciu=True)
sprawdz("4d hak, Use otworzył, krok po Use zgubiony: kolejny obieg krokiem, nie drugim Use", s.poz[0] >= 32505 and len(s.uzycia) == 1 and STAN["otwarte"],
        f"poz={s.poz} uz={s.uzycia} w={w}")
if HAS:
    cavebot.DRZWI_NAJPIERW_KROK = 0
    s, b, w = hak(otwarte=True, zgub=1)
    sprawdz("4e pokrętło 0, hak: stare zachowanie - Use bez próby kroku (zamyka otwarte)", len(s.uzycia) >= 1,
            f"uz={s.uzycia} kroki={s.kroki[:3]}")
    cavebot.DRZWI_NAJPIERW_KROK = 1
cavebot.PATROL_DRZWI = pd0

# --- 5. pokrętło w ZAKRESY / przykładzie ---
import json as _json2
import pokretla
sprawdz("5a pokrętło w pokretla.ZAKRESY i KIERUNEK", "DRZWI_NAJPIERW_KROK" in pokretla.ZAKRESY and "DRZWI_NAJPIERW_KROK" in pokretla.KIERUNEK)
sprawdz("5b na_zywo.przyklad.json: DRZWI_NAJPIERW_KROK=1",
        _json2.loads((KAT / "na_zywo.przyklad.json").read_text()).get("DRZWI_NAJPIERW_KROK") == 1)
sprawdz("5c domyślnie włączone w cavebot", getattr(cavebot, "DRZWI_NAJPIERW_KROK", None) == 1)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
