import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""27.10: rola kontenera z położenia okna (loot.rola_strukturalna: pole `rodzic` z kontenery.py) przed regułami z nazwy/ID/zawartości.
Układ odchyd/kolanoth: dwa okna 'Blue backpack', zewnętrzne (w ekwipunku) w ~76% z blankami było błędnie uznane za pojemnik na runy.
Offline, atrapy. Uruchom: python3 -I testy/test_loot_rodzic.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from PIL import Image, ImageDraw

import loot
import okna_start
import uh

ok = True


def sprawdz(opis, warunek, info=""):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis, "" if warunek else info)
    ok &= bool(warunek)


BLANK, UH, GOLD, BAG, SHOVEL, RED = 3147, 3160, 3031, 2869, 3457, 3582


def kon(numer, nazwa, ident, przedm, rodzic="brak", poj=20):
    k = {"numer": numer, "nazwa": nazwa, "id": ident, "pojemnosc": poj,
         "przedmioty": [{"slot": i, "id": a, "ilosc": 1} for i, a in enumerate(przedm)]}
    if rodzic != "brak":
        k["rodzic"] = rodzic
    return k


EKW = {"typ": "ekwipunek", "slot": 3}
WEWN = {"typ": "kontener", "numer": 1, "w_ekwipunku": 3}
# odchyd/kolanoth: zewnętrzne okno 13 blanków + 4 inne (76%), wewnętrzne 5 blanków + 2 UH
ZEWN_P = [BLANK] * 13 + [GOLD, BAG, SHOVEL, RED]
WEWN_P = [BLANK] * 5 + [UH] * 2

# 1. bez pola rodzic: dawne zachowanie (oba okna to runy, plecaków 0) - fallback
z0, w0 = kon(1, "blue backpack", BAG, ZEWN_P), kon(0, "blue backpack", BAG, WEWN_P)
sprawdz("1a bez rodzica: oba okna = runy (stary błąd klasyfikatora zostaje jako fallback)", loot.rola_kontenera(z0) == "runy" and loot.rola_kontenera(w0) == "runy")
# 2. z rodzicem: zewnętrzne = plecak, wewnętrzne = runy
z, w = kon(1, "blue backpack", BAG, ZEWN_P, EKW), kon(0, "blue backpack", BAG, WEWN_P, WEWN)
sprawdz("2a zewnętrzne (ekwipunek, slot 3) = plecak mimo 76% blanków", loot.rola_kontenera(z) == "plecak" and loot.czy_plecak(z) and not loot.czy_runy(z))
sprawdz("2b wewnętrzne (w plecaku z ekwipunku) = runy", loot.rola_kontenera(w) == "runy" and loot.czy_runy(w) and not loot.czy_plecak(w))
sprawdz("2c okna_start: plecaków 1, runy 1, bez problemów",
        (lambda r: (sum(x["rola"] == "plecak" for x in r), sum(x["rola"] == "runy" for x in r)))(okna_start.role_z_pamieci([w, z])) == (1, 1)
        and okna_start.ocen({"minimapa": "zwinieta", "prawo": 1, "plecak_ekw": (1, 1)}, okna_start.role_z_pamieci([w, z]))["problemy"] == [])
sprawdz("2d okna_start na starej klasyfikacji (bez rodzica) = brak_plecaka (dowód błędu sprzed zmiany)",
        [p["kod"] for p in okna_start.ocen({"minimapa": "zwinieta", "prawo": 1, "plecak_ekw": (1, 1)}, okna_start.role_z_pamieci([w0, z0]))["problemy"]] == ["brak_plecaka"])
sprawdz("2e UH: _plecak/_runy znajdują oba okna", uh._plecak([w, z]) is z and uh._runy([w, z]) is w)
sprawdz("2f UH na starej klasyfikacji: _plecak None (brak_plecaka), dowód błędu", uh._plecak([w0, z0]) is None)
# 3. normalne układy (rodzic ustalony): bez zmian ról
plecak = kon(0, "backpack", 2854, [GOLD, 2865, 3035, BLANK], EKW)
zielony = kon(1, "green backpack", 2865, [3198] * 16 + [BLANK] * 4, {"typ": "kontener", "numer": 0, "w_ekwipunku": 3})
sprawdz("3a gerbor: plecak=plecak, green backpack=runy", loot.rola_kontenera(plecak) == "plecak" and loot.rola_kontenera(zielony) == "runy")
purple = kon(1, "purple backpack", 2868, [UH] * 3, {"typ": "kontener", "numer": 0, "w_ekwipunku": 3})
sprawdz("3b Purple backpack w plecaku = runy", loot.rola_kontenera(purple) == "runy")
pusty = kon(1, "bag", 2853, [], {"typ": "kontener", "numer": 0, "w_ekwipunku": 3})
sprawdz("3c pusty bag w plecaku = runy (dawna reguła uznawała go za drugi plecak)", loot.rola_kontenera(pusty) == "runy")
# 4. fallback: rodzic nieznany / niejednoznaczny / zwłoki / depo
for opis, r in (("rodzic None", None), ("typ korzen (brak tablicy ekwipunku)", {"typ": "korzen"}), ("typ inne", {"typ": "inne"}),
                ("kontener nieznany (numer None)", {"typ": "kontener", "numer": None, "w_ekwipunku": None}),
                ("kontener w zwłokach", {"typ": "kontener", "numer": 5, "w_ekwipunku": None}),
                ("ekwipunek inny slot", {"typ": "ekwipunek", "slot": 10})):
    a, b = kon(1, "blue backpack", BAG, ZEWN_P, r), kon(0, "blue backpack", BAG, WEWN_P, r)
    sprawdz(f"4 {opis}: role jak dotąd (z zawartości)", loot.rola_kontenera(a) == loot.rola_kontenera(z0) and loot.rola_kontenera(b) == loot.rola_kontenera(w0))
sprawdz("4g zwłoki 'dead rat' (rodzic inne) = zwłoki", loot.rola_kontenera(kon(2, "dead rat", 3994, [GOLD, GOLD], {"typ": "inne"})) == "zwloki")
sprawdz("4h depo 'depot chest' zagnieżdżone bez znanego rodzica = zwłoki/nie plecak (jak dotąd)",
        loot.rola_kontenera(kon(2, "depot chest", 3502, [GOLD], {"typ": "kontener", "numer": None, "w_ekwipunku": None})) == "zwloki")
sprawdz("4i wewnętrzny zwykły bag z lootem obcym i bez run: strukturalnie nie rozstrzygamy (fallback = plecak z nazwy)",
        loot.rola_strukturalna(kon(2, "bag", 2853, [GOLD, SHOVEL, RED], WEWN)) is None
        and loot.rola_kontenera(kon(2, "bag", 2853, [GOLD, SHOVEL, RED], WEWN)) == "plecak")
sprawdz("4j dwa równorzędne plecaki w ekwipunku (oba rodzic korzen): stare reguły", loot.rola_strukturalna(kon(0, "backpack", 2854, [GOLD], {"typ": "korzen"})) is None)

# 5. loot.plan na zrzucie z dwoma oknami: plecak i runy rozpoznane bez rozstrzygania heurystyką z blanki_start
def okno_syn(im, x, y, wiersze, zajete=()):
    d = ImageDraw.Draw(im)
    for r in range(wiersze):
        for c in range(4):
            x0, y0 = x + c * 37, y + r * 37
            d.rectangle((x0, y0, x0 + 33, y0 + 33), outline=loot.RAMKA)
            if r * 4 + c in zajete:
                d.rectangle((x0 + 8, y0 + 8, x0 + 24, y0 + 24), fill=(200, 60, 160))
                d.rectangle((x0 + 12, y0 + 12, x0 + 20, y0 + 20), fill=(60, 200, 120))


im = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im, 580, 100, 5, zajete=range(7))
okno_syn(im, 580, 400, 5, zajete=range(17))
loot._zapytaj = lambda zad: {"kontenery": [w, z]}
pr = loot.plan(im, [])
sprawdz("5a loot.plan z rodzicami: plecak = zewnętrzne (17 przedmiotów), runy = wewnętrzne (7)", pr["plecak"] is not None and pr["runy"] is not None
        and len(pr["plecak"].kontener["przedmioty"]) == 17 and len(pr["runy"].kontener["przedmioty"]) == 7, (pr["plecak"], pr["runy"], pr["pamiec"]))
loot._zapytaj = lambda zad: {"kontenery": [w0, z0]}
pr0 = loot.plan(im, [])
sprawdz("5b loot.plan bez rodziców: plecak None (stary błąd, fallback)", pr0["plecak"] is None)

print("\nWYNIK:", "OK" if ok else "BŁĘDY")
sys.exit(0 if ok else 1)
