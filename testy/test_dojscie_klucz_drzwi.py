"""24.10 (Karol: „niech się nauczy otwierać drzwi”, Marinarra, start 15:44): dojście (wtedy abdendriel_z9_do_z10, od 24.10 19:xx abdendriel_depo_do_z10) z korytarza z9 (32654,31656) nie przechodziło
przez DWOJE drzwi zamkniętych na klucz (32655,31655,z9) i (32658,31645,z9) (w mapie ściany): A* bez drogi, krok w ścianę, KROK_ZLY, porażka S1.
Poprawka: cavebot._drzwi_lista dopisuje (tylko w dojściu) drzwi z wyprawa.PLANY_PK["klucze"] (jedno źródło kluczy = generuj_powrot_abdendriel.KLUCZE_DRZWI),
A* prowadzi przez nie, a _drzwi_hak przy drzwiach z kluczem robi to samo co wypad._drzwi: krok, KLUCZ (Ctrl+klik na kluczu, klik na drzwiach), krok.
Atrapy z test_patrol_troll.py (prawdziwa mapa i trasa), bez gry (RETRONIC_TESTY=1). Model: drzwi otwiera TYLKO klucz (zwykłe Use nic nie robi),
krok na kafelek zamkniętych drzwi nie rusza postaci. NIEZWERYFIKOWANE NA ŻYWO: czy klucz 2970 pasuje do obu drzwi."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_patrol_troll.py").read_text()
_src = _src[:_src.index("# 2. patrol wizytuje")]
_g = {"__file__": str(KAT / "testy" / "test_patrol_troll.py"), "__name__": "atrapy_patrol_troll"}
exec(compile(_src, "test_patrol_troll(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()
import json as _json
import generuj_powrot_abdendriel as G
import wyprawa
import mozg
import wypad

if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test")
    sys.exit(0)

DRZWI_A, DRZWI_B = (32658, 31645, 9), (32655, 31655, 9)
KLUCZ = 2970
OTWARTE = set()
f_stary = _g["f"]


def f_k(x, y, z):
    v = M.flagi(x, y, z)
    if (x, y, z) in LADOWANIA:
        v &= ~2
    if (x, y, z) in (DRZWI_A, DRZWI_B):
        return (v | 1) & ~4 if (x, y, z) in OTWARTE else (v | 1 | 4)
    return v


_g["f"] = f_k


class SwiatK(Swiat):
    """Drzwi na klucz: otwiera je tylko uzyj_klucz z pola obok (<= 1 pole); zwykłe Use (uzyj) nic nie robi. Klucz może nie leżeć w plecaku."""
    def __init__(s, poz, klucz_w_plecaku=True, **kw):
        super().__init__(poz, **kw)
        s.klucz_w_plecaku = klucz_w_plecaku
        s.klucze = []            # (id, drzwi, pozycja postaci, liczba kroków przed)
        s.kroki = []             # (klawisz, pozycja przed)
        s.zwykle_use = []

    def uzyj(s, pole):
        s.zwykle_use.append(tuple(pole))


class PK(P):
    def krok(p, k):
        p.s.kroki.append((k, tuple(p.s.poz)))
        return P.krok(p, k)

    def klawisz(p, k):
        p.krok(k)


class OpsK(Ops):
    def uzyj_klucz(o, id_klucza, cel, poz):
        s = o.s
        if not s.klucz_w_plecaku:
            raise wypad.BrakPrzedmiotu("brak klucza w otwartych pojemnikach")
        cel = tuple(cel)
        s.klucze.append((int(id_klucza), cel, tuple(poz), len(s.kroki)))
        s.t += 0.3
        if max(abs(cel[0] - poz[0]), abs(cel[1] - poz[1])) <= 1 and cel in (DRZWI_A, DRZWI_B):
            OTWARTE.add(cel)


def dojscie_k(start, nazwa="abdendriel_depo_do_z10", klucz_w_plecaku=True, maks=2500, limit_s=240.0, zdarzenie=None):
    LOG.clear()
    OTWARTE.clear()
    s = SwiatK(start, klucz_w_plecaku=klucz_w_plecaku)
    punkty = [tuple(p) for p in _json.loads((KAT / "trasy" / f"{nazwa}.json").read_text())]
    punkty = mozg.dojscie_od_pozycji(punkty, tuple(start))      # jak mozg.przejdz_dojscie: trasa od najbliższego punktu (24.10: dojście zaczyna się teraz w depo z8)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.CavebotDojscie(PK(s), punkty, okrazenia=1, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij,
                               zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, tolerancja=2)
    b.pietra_ops = OpsK(s)
    b.zapis_znanych = False
    n = 0
    while n < maks and s.t < limit_s and b.tick():
        n += 1
        s.t += 0.05
        if zdarzenie:
            zdarzenie(s, b, n)
    return s, b, n


START = (32654, 31656, 9)
KONIEC = (32668, 31624, 10)

# --- 0. jedno źródło kluczy ---
zrodlo = {tuple(d): int(k) for p in wyprawa.PLANY_PK for d, k in (p.get("klucze") or ())}
sprawdz("0a źródło kluczy PLANY_PK == generuj_powrot_abdendriel.KLUCZE_DRZWI (dwoje drzwi, klucz 2970)",
        zrodlo == {tuple(d): int(k) for d, k in G.KLUCZE_DRZWI} == {DRZWI_A: KLUCZ, DRZWI_B: KLUCZ}, f"{zrodlo}")
sprawdz("0b w mapie oba drzwi to ściana (flaga 4), a pola obok przechodnie",
        all(M.flagi(*d) & 4 for d in (DRZWI_A, DRZWI_B)) and M.flagi(32655, 31656, 9) & 1 and M.flagi(32655, 31654, 9) & 1)

# --- 1. start z korytarza z9 (jak 15:44): dojście dochodzi do jaskini i na z10 ---
s, b, n = dojscie_k(START)
sprawdz("1a start (32654,31656,z9): dojście kończy się na z10 (32668,31624), bez porażki",
        tuple(s.poz) == KONIEC and not b.dojscie_porazka, f"poz={s.poz} porazka={b.dojscie_porazka} t={s.t:.0f}s ticki={n}")
sprawdz("1b oba drzwi otwarte kluczem 2970 (po jednym użyciu klucza na drzwiach, w tej kolejności: B potem A)",
        [k[:2] for k in s.klucze[:2]] == [(KLUCZ, DRZWI_B), (KLUCZ, DRZWI_A)] and OTWARTE == {DRZWI_A, DRZWI_B}, f"{s.klucze}")
sprawdz("1c klucz użyty z pola obok drzwi (w osi), nie z odległości", all(max(abs(c[2][0] - c[1][0]), abs(c[2][1] - c[1][1])) == 1
                                                                 and c[2][0] == c[1][0] for c in s.klucze), f"{s.klucze}")
sprawdz("1d zwykłe Use na drzwiach nigdy (drzwi na klucz)", not [u for u in s.zwykle_use if u in (DRZWI_A, DRZWI_B)], f"{s.zwykle_use}")
# wzorzec wypad._drzwi: PRZED kluczem krok w stronę drzwi, PO kluczu krok
for d in (DRZWI_B, DRZWI_A):
    ik = next((i for i, c in enumerate(s.klucze) if c[1] == d), None)
    if ik is None:
        sprawdz(f"1e kolejność krok, klucz, krok przy drzwiach {d[:2]}", False, "brak użycia klucza")
        continue
    nk = s.klucze[ik][3]
    przed = [k for k in s.kroki[:nk] if k[1] == s.klucze[ik][2]]
    sprawdz(f"1e kolejność krok, klucz, krok przy drzwiach {d[:2]}: krok z pola obok przed kluczem",
            len(przed) >= 1, f"kroki przed={s.kroki[max(0, nk - 3):nk]}")
    po = s.kroki[nk:nk + 1]
    sprawdz(f"1f krok na drzwi zaraz po kluczu przy {d[:2]}", len(po) == 1 and po[0][0] in ("Up", "Down", "Left", "Right"), f"po={po}")
sprawdz("1g żaden krok w ścianę (nie ma 'nie ruszył' ani KROK_ZLY w logu)", not [l for l in LOG if "nie ruszył" in l or "KROK_ZLY" in l],
        [l for l in LOG if "nie ruszył" in l or "KROK_ZLY" in l][:3])

# --- 2. start w sali między drzwiami (po otwarciu B zamknięte A) i start w jaskini za drzwiami ---
s2, b2, n2 = dojscie_k((32657, 31650, 9))
sprawdz("2a start w sali między drzwiami: tylko drzwi A kluczem, kończy na z10",
        tuple(s2.poz) == KONIEC and [c[1] for c in s2.klucze] == [DRZWI_A], f"poz={s2.poz} klucze={s2.klucze}")
s3, b3, n3 = dojscie_k((32658, 31644, 9))
sprawdz("2b start w jaskini za drzwiami: żadnego klucza, kończy na z10", tuple(s3.poz) == KONIEC and not s3.klucze, f"poz={s3.poz} klucze={s3.klucze}")

# --- 3. brak klucza w plecaku: nie wisi w nieskończoność, nie bije w ścianę, jasny wpis w logu ---
s4, b4, n4 = dojscie_k(START, klucz_w_plecaku=False, limit_s=120.0)
sprawdz("3a brak klucza: dojście nie dochodzi (drzwi zamknięte) i nie wpada na z10", tuple(s4.poz)[2] == 9 and tuple(s4.poz) != KONIEC, f"poz={s4.poz}")
sprawdz("3b brak klucza: wpis o braku klucza w logu", any("klucz" in l.lower() and "brak" in l.lower() for l in LOG), LOG[-5:])

# --- 4. klucze tylko w dojściu: zwykły Cavebot (patrol/trasa) nie traktuje drzwi na klucz jako przejścia ---
loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
sw = SwiatK(START)
bz = cavebot.Cavebot(PK(sw), [START, (32655, 31654, 9)], zapytaj=sw.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=sw.spij,
                     zegar=sw.zegar, loot=loot, mapa=M, klik=sw.klik)
sprawdz("4a zwykły Cavebot: drzwi na klucz nie są w liście drzwi", DRZWI_A[:2] not in bz._drzwi_xy(9) and DRZWI_B[:2] not in bz._drzwi_xy(9), f"{bz._drzwi_xy(9)}")
bd = cavebot.CavebotDojscie(PK(sw), [START, (32655, 31654, 9)], okrazenia=1, zapytaj=sw.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                            spij=sw.spij, zegar=sw.zegar, loot=loot, mapa=M, klik=sw.klik, tolerancja=2)
sprawdz("4b CavebotDojscie: oba drzwi na klucz są przejściem (z9)", {DRZWI_A[:2], DRZWI_B[:2]} <= set(bd._drzwi_xy(9)), f"{bd._drzwi_xy(9)}")

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
