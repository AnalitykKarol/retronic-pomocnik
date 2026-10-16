#!/usr/bin/env python3
"""F1 (17.10): zawieszka z drzwiami (32505,32270,z8) odtworzona na atrapach (hipoteza SPEC_model_steruje_gra_1016 7.8).
Scenariusz: bot stoi po wschodniej stronie drzwi (dystans >= 2), drzwi FAKTYCZNIE zamknięte, a flaga `otw` w drzwi_stan
została z poprzedniego przejścia (=True). `_drzwi_hak` w patrolu nie podchodzi (`not st["otw"]`) i nie robi Use (dystans >= 2),
więc bot stoi bez końca. Poprawka: DRZWI_PONOW=1 (domyślnie 0) traktuje flagę starszą niż DRZWI_STARA_S jako przeterminowaną.
Atrapy z test_poscig_skosy_drzwi.py (prawdziwa mapa i miejsca_troll.json), bez gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_poscig_skosy_drzwi.py").read_text()
_src = _src[:_src.index("LOGR = LOG")]                      # tylko atrapy (Swiat2, zrob2, poscig), bez ich testów
_g = {"__file__": str(KAT / "testy" / "test_poscig_skosy_drzwi.py"), "__name__": "atrapy_drzwi"}
exec(compile(_src, "test_poscig_skosy_drzwi(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()
import random  # noqa: E402

PONOW0 = getattr(cavebot, "DRZWI_PONOW", None)             # None = kod sprzed F1 (brak pokrętła)
PD0 = cavebot.PATROL_DRZWI
cavebot.PATROL_DRZWI = 1
CEL = "z8_spawn_32500_32270"                                # miejsce na zachód od drzwi
LIMIT_S = 120.0                                             # "nie stoi bez końca" = cel albo Use w tyle s symulowanych


def patrol_przez_drzwi(poz0, otw, otw_t=None, drzwi_dzialaja=True, drzwi_otwarte_od_poczatku=False, n=3000):
    random.seed(1)
    LOG.clear()
    s = Swiat2(START, gora="use", drzwi_dzialaja=drzwi_dzialaja)
    s.poz[:] = list(poz0)
    if drzwi_otwarte_od_poczatku:
        STAN["otwarte"] = True
    b = zrob2(s, list(troll), okrazenia=999)
    b._patrol_wczytaj()
    m = next(x for x in b.miejsca if x["nazwa"] == CEL)
    st = {"poz": None, "t0": -999.0, "proby": 0, "zle_do": float("-inf"), "nota": False, "otw": otw}
    if otw_t is not None:
        st["otw_t"] = otw_t
    b.drzwi_stan[DR] = st
    b.patrol = b._patrol_nowy(tuple(s.poz), m, "test", waga=1.0)
    b.patrol_pierwszy = False
    for _ in range(n):
        if not b.tick() or s.t > LIMIT_S:
            break
        if any(q[:2] == (m["x"], m["y"]) and q[2] == 8 for q in s.odwiedzone):
            break
    dosz = any(q[:2] == (m["x"], m["y"]) and q[2] == 8 for q in s.odwiedzone)
    return dosz, s, b


E1, E2 = (32507, 32270, 8), (32508, 32270, 8)

# 0. punkt odniesienia: drzwi zamknięte, flaga uczciwa (otw=False) -> Use i przejście (to działa dziś)
cavebot.DRZWI_PONOW = 0
d, s, b = patrol_przez_drzwi(E1, False)
sprawdz("0 flaga otw=False: Use i dojście do celu (zachowanie dziś)", d and DR in s.uzycia, f"{d} uz={s.uzycia} t={s.t:.0f}")

# 1. DRZWI_PONOW=1: przeterminowana flaga otw=True + zamknięte drzwi, dystans 2 i 3 -> bot NIE stoi bez końca
for poz0 in (E1, E2):
    cavebot.DRZWI_PONOW = 1
    d, s, b = patrol_przez_drzwi(poz0, True)
    sprawdz(f"1 DRZWI_PONOW=1, stara flaga otw, start {poz0[:2]}: Use i dojście do celu w <= {LIMIT_S:.0f} s",
            d and DR in s.uzycia and s.t <= LIMIT_S, f"{d} uz={s.uzycia} poz={s.poz} t={s.t:.0f}")

# 2. to samo przy DRZWI_PONOW=0: usterka odtworzona (bot stoi, brak Use) — dokumentuje stan domyślny, nie jest zaleceniem
cavebot.DRZWI_PONOW = 0
d, s, b = patrol_przez_drzwi(E1, True)
sprawdz("2 DRZWI_PONOW=0 (domyślnie): zawieszka odtworzona, brak Use i brak dojścia", (not d) and DR not in s.uzycia, f"{d} uz={s.uzycia} poz={s.poz} t={s.t:.0f}")

# 3. świeża flaga (staliśmy na drzwiach przed chwilą) nie jest zmieniana przez poprawkę: zachowanie jak przy 0
cavebot.DRZWI_PONOW = 1
d3, s3, b3 = patrol_przez_drzwi(E1, True, otw_t=0.0)           # zegar atrapy t=0: flaga ma 0 s, DRZWI_STARA_S = 20 s
cavebot.DRZWI_PONOW = 0
d3b, s3b, b3b = patrol_przez_drzwi(E1, True, otw_t=0.0)
sprawdz("3 świeża flaga: PONOW=1 nie zmienia zachowania względem 0 (brak podejścia wcześniej niż po DRZWI_STARA_S)",
        d3b is False and DR not in s3b.uzycia and (d3 is False or s3.t >= cavebot.DRZWI_STARA_S - 1e-9 or DR not in s3.uzycia),
        f"pon1: {d3} uz={s3.uzycia} t={s3.t:.0f} | pon0: {d3b} uz={s3b.uzycia}")

# 4. drzwi naprawdę otwarte, flaga przeterminowana: PONOW=1 przechodzi bez Use
cavebot.DRZWI_PONOW = 1
d, s, b = patrol_przez_drzwi(E1, True, drzwi_otwarte_od_poczatku=True)
sprawdz("4 PONOW=1, drzwi otwarte: dojście bez Use", d and DR not in s.uzycia, f"{d} uz={s.uzycia} t={s.t:.0f}")

# 5. drzwi niedziałające, PONOW=1: max DRZWI_PROB Use, potem odpuszczenie (bez pętli Use)
d, s, b = patrol_przez_drzwi(E1, True, drzwi_dzialaja=False)
sprawdz("5 PONOW=1, drzwi niedziałające: Use <= DRZWI_PROB", s.uzycia.count(DR) <= cavebot.DRZWI_PROB, f"uz={len(s.uzycia)}")

# 6. pokrętło: domyślnie 0, w ZAKRESY, w przykładzie z domyślną, niedostępne dla analityka w górę
import json  # noqa: E402
import pokretla  # noqa: E402
przyklad = json.loads((KAT / "na_zywo.przyklad.json").read_text())
sprawdz("6a DRZWI_PONOW w ZAKRESY i w na_zywo.przyklad.json = 0", "DRZWI_PONOW" in pokretla.ZAKRESY and przyklad.get("DRZWI_PONOW") == 0)
sprawdz("6b domyślna w kodzie = 0 (przed testem)", PONOW0 in (0, None), PONOW0)

cavebot.DRZWI_PONOW = PONOW0 if PONOW0 is not None else 0
cavebot.PATROL_DRZWI = PD0
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
