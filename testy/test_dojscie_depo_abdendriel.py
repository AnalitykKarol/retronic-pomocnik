"""24.10 19:12 (Marinarra, depo Ab'Dendriel (32679,31687,z8), start `MAPA=abdendriel_trolle_z10_z9`): dojście abdendriel_z9_do_z10 zaczynało się w jaskini z9, więc start z depo
kończył się „Przejście pięter BEZ kandydatów: z8 … -> z9 … Dojście nieukończone … nie zaczynam głównej trasy”. Teraz mapa używa dojścia abdendriel_depo_do_z10
(generuj_powrot_abdendriel.py --zapisz): JEDNA droga z depo przez schody w dół (z8 -> z9), oboje drzwi na klucz 2970 i jaskinię z9 do dziury (32668,31624) -> z10,
a z dowolnego jej punktu (też z z8) mozg.dojscie_od_pozycji bierze najbliższy punkt. Wyjście serwisu Ab'Dendriel leży na tej samej drodze.
Atrapy i świat jak w test_dojscie_klucz_drzwi.py (prawdziwa mapa i trasa, bez gry). NIEZWERYFIKOWANE NA ŻYWO: schody z8->z9 od depo, klucz 2970 w obu drzwiach, dziura z9->z10."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_dojscie_klucz_drzwi.py").read_text()
_src = _src[:_src.index("# --- 0. jedno źródło kluczy")]
_g = {"__file__": str(KAT / "testy" / "test_dojscie_klucz_drzwi.py"), "__name__": "atrapy_dojscie_klucz"}
exec(compile(_src, "test_dojscie_klucz_drzwi(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()
import io
import contextlib

NAZWA = "abdendriel_depo_do_z10"
SCIEZKA = KAT / "trasy" / f"{NAZWA}.json"
DEPO = (32679, 31687, 8)
DRZWI_B_, DRZWI_A_ = (32655, 31655, 9), (32658, 31645, 9)       # kolejność przejścia z depo: najpierw (32655,31655), potem (32658,31645)
DOJ = [tuple(q) for q in _json.loads(SCIEZKA.read_text())]
META = _json.loads(SCIEZKA.with_suffix(".meta").read_text())["specjalne"]
MAPY = _json.loads((KAT / "mapy.json").read_text())


def halas():
    """Zderzenia z murem przy podejściu do drzwi i przejść (to łapał błąd z 19:12 i wcześniejsze KROK_ZLY)."""
    return [l for l in LOG if "KROK_ZLY" in l or "BEZ kandydatów" in l or "NIEUDANE" in l or "porażk" in l or "Dojście: przejście pięter" in l]


def mur():
    """Zderzenia z murem na z8 i na z9 po stronie korytarza/drzwi (y >= 31644): tu łapaliśmy brak drzwi-hooka. Zakręt jaskini tuż przed dziurą (32663,31628) atrapa
    chodzenia klikiem przecina losowo (DROGA_DO_PRZODU = random), serwer w grze ścieżkę wytycza sam: to szum atrapy, nie błąd trasy."""
    import re
    wyn = []
    for l in LOG:
        m_ = re.search(r"krok \w+ z \((\d+), (\d+), (\d+)\) nie ruszył", l)
        if m_ and (int(m_.group(3)) == 8 or int(m_.group(2)) >= 31644):
            wyn.append(l)
    return wyn


# --- 1. mapa i plik -------------------------------------------------------------------------------------------------------
w = MAPY["abdendriel_trolle_z10_z9"]
sprawdz("1a mapy.json: abdendriel_trolle_z10_z9 używa dojścia abdendriel_depo_do_z10 z dojscie_z_dowolnego_pietra (najbliższy punkt także z z8)",
        w.get("dojscie") == NAZWA and w.get("dojscie_z_dowolnego_pietra") is True and w.get("trasa") == "abdendriel_trolle_z10_petla", f"{w.get('dojscie')} {w.get('dojscie_z_dowolnego_pietra')}")
_petla = [tuple(q) for q in _json.loads((KAT / "trasy" / "abdendriel_trolle_z10_petla.json").read_text())]
sprawdz("1b dojście zaczyna się w depo (32679,31687,z8) i kończy na (32668,31624,z10), 1 pole od punktu pętli z10 (jak dawne dojście z z9)",
        DOJ[0] == DEPO and DOJ[-1] == KONIEC and min(max(abs(q[0] - KONIEC[0]), abs(q[1] - KONIEC[1])) for q in _petla if q[2] == 10) <= 1, f"{DOJ[0]} {DOJ[-1]}")
sprawdz("1c punkty na trzech piętrach w tej kolejności: z8 (korytarz), z9 (korytarz, sala, jaskinia), z10 (jeden punkt)",
        [q[2] for q in DOJ] == sorted(q[2] for q in DOJ) and {q[2] for q in DOJ} == {8, 9, 10} and sum(1 for q in DOJ if q[2] == 10) == 1)
with contextlib.redirect_stdout(io.StringIO()):
    gen, gmeta = G.zbuduj_dojscie()
sprawdz("1d generator jest źródłem prawdy: wynik generatora == plik trasy i meta", [tuple(q) for q in gen] == DOJ and _json.loads(_json.dumps(gmeta, ensure_ascii=False)) == META)
sprawdz("1e dawne dojście abdendriel_z9_do_z10 (od z9) wycofane z trasy/, mapy.json już go nie używa",
        not (KAT / "trasy" / "abdendriel_z9_do_z10.json").exists() and all(v.get("dojscie") != "abdendriel_z9_do_z10" for v in MAPY.values() if isinstance(v, dict)))

# --- 2. jedna droga: dojście == powrót odwrócony (+ dziura), serwis na tej samej drodze ------------------------------------
POW = [tuple(q) for q in _json.loads((KAT / "trasy" / "abdendriel_trolle_do_depo.json").read_text())]
drzwi_komorki = set(G.DRZWI9)
dojs = set(DOJ) - {G.DZIURA9, G.LAD10} - drzwi_komorki
sprawdz("2a dojście nie ma własnej geometrii: każdy jego punkt (poza dziurą z9, polem liny z10 i polami drzwi) leży na trasie powrotu do depo",
        dojs <= set(POW), sorted(dojs - set(POW))[:5])
sprawdz("2b i odwrotnie: powrót nie ma odcinka, którego dojście nie zna (poza startem z10 i lądowaniem schodów w górę z8)",
        set(POW) - {POW[0], G.LAD8} <= set(DOJ), sorted(set(POW) - {POW[0], G.LAD8} - set(DOJ))[:5])
idx_drzwi = [DOJ.index(d) for d in (DRZWI_B_, DRZWI_A_)]
sprawdz("2c pola obojga drzwi są punktami trasy, w kolejności (32655,31655) potem (32658,31645), z polami po obu stronach",
        None not in idx_drzwi and idx_drzwi[0] < idx_drzwi[1] and all(
            abs(DOJ[i - 1][0] - DOJ[i][0]) + abs(DOJ[i - 1][1] - DOJ[i][1]) == 1 and abs(DOJ[i + 1][0] - DOJ[i][0]) + abs(DOJ[i + 1][1] - DOJ[i][1]) == 1 for i in idx_drzwi))
sprawdz("2d meta: dwa wpisy 'drzwi' z kluczem 2970 na tych indeksach; wpis 'wyjscie_serwisu' ZA obojgiem drzwi",
        sorted(e["idx"] for e in META if e["typ"] == "drzwi" and e.get("klucz") == KLUCZ) == idx_drzwi and
        [e["idx"] for e in META if e["typ"] == "wyjscie_serwisu"] == [DOJ.index(G.WYJSCIE_SERWISU)] and DOJ.index(G.WYJSCIE_SERWISU) > idx_drzwi[1])
import generuj_serwis_abdendriel as GS
sp = _json.loads((KAT / "trasy" / "serwis_abdendriel.json").read_text())
sprawdz("2e serwis_abdendriel: krok 'wyjscie' = punkt tej samej drogi (dojścia) za obojgiem drzwi: jedno źródło",
        tuple(sp["wyjscie"]) == tuple(G.WYJSCIE_SERWISU) and tuple(sp["wyjscie"]) in DOJ and DOJ.index(tuple(sp["wyjscie"])) > idx_drzwi[1], sp.get("wyjscie"))

# --- 3. trasa liczona od pozycji (mozg.dojscie_od_pozycji): z depo od z8, z z9 od z9 ---------------------------------------
for nazwa, st, pierwsze_piętro, min_idx in [("depo", DEPO, 8, 0), ("korytarz z8", (32655, 31675, 8), 8, 1), ("lądowanie schodów z9", (32655, 31671, 9), 9, 1),
                                          ("korytarz z9", (32655, 31660, 9), 9, 1), ("jaskinia z9", (32660, 31640, 9), 9, 1)]:
    t = mozg.dojscie_od_pozycji(DOJ, st)
    sprawdz(f"3 {nazwa} {st}: trasa zaczyna się na piętrze postaci z{pierwsze_piętro}, nie na z9/ścianie, kończy na z10 (32668,31624)",
            t and t[0][2] == st[2] == pierwsze_piętro and t[-1] == KONIEC and DOJ.index(t[0]) >= min_idx - 1, f"{t[:2]}")

# --- 4. start z depo: plan przez oba drzwi do pętli z10 --------------------------------------------------------------------
s, b, n = dojscie_k(DEPO, nazwa=NAZWA)
sprawdz("4a start (32679,31687,z8): dojście kończy się na z10 (32668,31624) bez porażki (do 24.10 19:12: BEZ kandydatów)",
        tuple(s.poz) == KONIEC and b.dojscie_ok and not b.dojscie_porazka, f"poz={s.poz} porazka={b.dojscie_porazka} t={s.t:.0f}s ticki={n}")
sprawdz("4b schody z8 -> z9 przez pole (32654,31670), potem OBA drzwi kluczem 2970 w kolejności (32655,31655), (32658,31645)",
        any("z8 -> z9" in l and "(32654, 31670" in l for l in LOG) and [k[:2] for k in s.klucze] == [(KLUCZ, DRZWI_B_), (KLUCZ, DRZWI_A_)] and OTWARTE == {DRZWI_A_, DRZWI_B_},
        f"{s.klucze} {[l for l in LOG if 'Przejście' in l][:3]}")
sprawdz("4c z depo zero zderzeń z murem (przy schodach, korytarzu i obojgu drzwi) i zero porażek/„BEZ kandydatów” w logu", not halas() and not mur(), (halas() + mur())[:3])
sprawdz("4d zwykłe Use na drzwiach nigdy (drzwi na klucz)", not [u for u in s.zwykle_use if u in (DRZWI_A_, DRZWI_B_)], f"{s.zwykle_use}")

# --- 5. start z każdego punktu drogi depo -> jaskinia ------------------------------------------------------------------------
wyniki = []
for nazwa, st, klucze_oczek in [("korytarz z8", (32655, 31675, 8), 2), ("lądowanie schodów z9", (32655, 31671, 9), 2), ("korytarz z9 przy drzwiach", (32654, 31656, 9), 2),
                                 ("sala między drzwiami", (32657, 31650, 9), 1), ("jaskinia za drzwiami (wyjście serwisu)", (32658, 31644, 9), 0),
                                 ("jaskinia przy dziurze", (32667, 31627, 9), 0)]:
    s5, b5, n5 = dojscie_k(st, nazwa=NAZWA)
    sprawdz(f"5 {nazwa} {st}: dochodzi na z10 (32668,31624), kluczy {klucze_oczek}, bez zderzeń i porażek",
            tuple(s5.poz) == KONIEC and not b5.dojscie_porazka and len(s5.klucze) == klucze_oczek and not halas(),
            f"poz={s5.poz} klucze={[k[1] for k in s5.klucze]} halas={halas()[:2]}")

# --- 6. brak klucza w plecaku: z depo dojście staje przy pierwszych drzwiach, nie wisi i nie bije w ścianę --------------------
s6, b6, n6 = dojscie_k(DEPO, nazwa=NAZWA, klucz_w_plecaku=False, limit_s=300.0)
sprawdz("6 start z depo bez klucza: nie dochodzi na z10, jasny wpis o braku klucza, próba kończy się porażką (strażnik postępu), nie wisi w nieskończoność",
        tuple(s6.poz)[2] == 9 and any("klucz" in l.lower() and "brak" in l.lower() for l in LOG) and b6.dojscie_porazka and s6.t < 300.0,
        f"poz={s6.poz} porazka={b6.dojscie_porazka} t={s6.t:.0f} {[l for l in LOG if 'klucz' in l][:2]}")

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
