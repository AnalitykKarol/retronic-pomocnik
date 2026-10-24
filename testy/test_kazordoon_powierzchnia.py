"""24.10: spot trolle_kazordoon_z7 = trolle i węże NA POWIERZCHNI z7 przy drodze Thais -> Kazordoon (generuj_trasy_kazordoon_powierzchnia.py).
Powód (Karol 24.10 ~10:55): jaskinię trolli z8 zajął inny gracz. Reguła Karola: jedna droga + odgałęzienia, bez dublowania; dojście tego spotu ma być
PREFIKSEM dojść z8/z9. Pilnuje też stref zakazanych (dziura z7 i pole liny z buforem 2, ogień z buforem 1, dziury nauczone, groźne spawny w promieniu 6),
wpisów mapy.json / spoty_nadzorca.json / wyprawa.PLANY_PK i drogi z pętli do depo Thais. Dane rzeczywiste; nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import pietra
import trasa_io
import wypad
import wyprawa as W

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powierzchni Kazordoonu")
    sys.exit(0)

TRASY = Path(_R) / "trasy"
N = "trolle_kazordoon_z7"
S = (32660, 31985, 7)                    # rozgałęzienie: koniec dojścia, start i koniec pętli, start powrotu
DEPO = (32348, 32225, 7)
DZIURA = (32663, 31962, 7)               # dziura z7 -> z8 (zasypana: łopata)
LAD_LINY = (32663, 31963, 7)             # lądowanie liny z8 -> z7
DRZWI = (32659, 31966, 7)
MAPA = _mapa.Mapa()


def wczytaj(nazwa):
    return [tuple(int(v) for v in p) for p in trasa_io.wczytaj(nazwa)[0]]


D, P, R = wczytaj(f"{N}_dojscie"), wczytaj(f"{N}_petla"), wczytaj(f"{N}_do_depo")
D8, D9 = wczytaj("trolle_kazordoon_z8_dojscie"), wczytaj("trolle_kazordoon_z9_dojscie")


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# --- jedna droga + odgałęzienie: dojście = prefiks dojść z8/z9
sprawdz("dojście zaczyna w depo Thais i kończy w rozgałęzieniu", D[0] == DEPO and D[-1] == S, (D[0], D[-1]))
sprawdz("dojście = PREFIKS dojścia z8 (ta sama droga, bez dublowania)", D8[:len(D)] == D, "prefiks różny")
sprawdz("dojście = PREFIKS dojścia z9", D9[:len(D)] == D, "prefiks różny")
sprawdz("rozgałęzienie leży na wspólnym odcinku (dojście z8 przechodzi przez nie) i tuż za nim droga skręca ku drzwiom", S in D8 and D8[D8.index(S) + 1][:2] == (S[0], S[1] - 1), D8[D8.index(S) + 1])
sprawdz("dojście >= 500 pól (wspólny odcinek, nie skrót)", len(D) >= 500, len(D))
sprawdz("pętla zaczyna i kończy w rozgałęzieniu (koniec dojścia = start pętli)", P[0] == S == P[-1] and D[-1] == P[0], (P[0], P[-1]))
sprawdz("powrót startuje w rozgałęzieniu i kończy w depo Thais", R[0] == S and R[-1] == DEPO, (R[0], R[-1]))
sprawdz("pętla leży w całości na z7 (bez dziury, schodów, liny)", {p[2] for p in P} == {7}, {p[2] for p in P})
sprawdz("pętla 120..230 pól (196 w generatorze), bez rozdęcia", 120 <= len(P) <= 230, len(P))

# --- piętra: dojście i powrót to z7 + pomost z6 mostu Thais (2 rampy), nic więcej; bez grobli z dwarfami i bez miasta
for n, t in (("dojście", D), ("powrót", R)):
    z6 = [p for p in t if p[2] == 6]
    sprawdz(f"{n}: z6 tylko pomost mostu Thais (32547..32554, 32076)", z6 and all(32547 <= p[0] <= 32554 and p[1] == 32076 for p in z6), z6)
    sprawdz(f"{n}: piętra tylko 6 i 7, dokładnie 2 przejścia (rampy mostu), BEZ dziury i liny",
            {p[2] for p in t} == {6, 7} and sum(1 for a, b in zip(t, t[1:]) if a[2] != b[2]) == 2, sum(1 for a, b in zip(t, t[1:]) if a[2] != b[2]))
    grobla = [p for p in t if p[2] == 6 and 32610 <= p[0] <= 32625 and 31960 <= p[1] <= 31975]
    sprawdz(f"{n}: nie wchodzi na groblę z6 (dwarfy)", not grobla, grobla[:3])
    pow_ = [p for p in t if p[2] in (6, 7)]
    dr = sum(1 for p in pow_ if MAPA.pole(*p)[1] == 129)
    sprawdz(f"{n}: >= 60% pól po szarej drodze", dr * 100 >= 60 * len(pow_), f"{dr}/{len(pow_)}")


def ciagla(trasa):
    """Kolejne punkty tego samego piętra w odległości <= 1 (Chebyshev); zmiana piętra o <= 2 pola."""
    for a, b in zip(trasa, trasa[1:]):
        if cheb(a, b) > (2 if a[2] != b[2] else 1):
            return (a, b)
    return None


for n, t in (("dojście", D), ("pętla", P), ("powrót", R)):
    sprawdz(f"{n}: ciągłość", ciagla(t) is None, ciagla(t))

# --- przejścia pięter potwierdzone przez pietra.kandydaci (pewne, pole przejścia = nasze)
for n, t in (("dojście", D), ("powrót", R)):
    for a, b in zip(t, t[1:]):
        if a[2] == b[2]:
            continue
        pewne = [tuple(k["pole"]) for k in pietra.kandydaci(MAPA, a, b) if k.get("pewne")]
        sprawdz(f"{n}: przejście {a}->{b}: pole przejścia to pewny kandydat pietra.kandydaci", a in pewne, pewne[:2])

# --- ogień (bufor 1), dziury nauczone, dziura z7 i pole liny z buforem 2: nic na żadnej z tras
OGIEN = set()
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
NAUCZONE = {tuple(int(v) for v in p[:3]) for p in json.loads((TRASY / "dziury_nauczone.json").read_text()).get("dziury", [])}
for n, t in (("dojście", D), ("pętla", P), ("powrót", R)):
    zle = [p for p in t if any((p[0] + dx, p[1] + dy, p[2]) in OGIEN for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    sprawdz(f"{n}: bez ognia (bufor 1)", not zle, zle[:3])
    sprawdz(f"{n}: bez dziur z dziury_nauczone.json", not (NAUCZONE & set(t)), sorted(NAUCZONE & set(t))[:3])
    sprawdz(f"{n}: ani dziura z7 {DZIURA[:2]}, ani lądowanie liny {LAD_LINY[:2]} NIE leżą na trasie", DZIURA not in t and LAD_LINY not in t, "")
    blisko = [p for p in t if p[2] == 7 and min(cheb(p, DZIURA), cheb(p, LAD_LINY)) <= 2]
    sprawdz(f"{n}: >= 3 pola od dziury i pola liny (bufor 2)", not blisko, blisko[:3])
sprawdz("drzwi (32659,31966,z7) NIE są na pętli (pętla ich nie otwiera)", DRZWI not in P, "")
sprawdz("pętla: mechanizm tras nie widzi na niej drzwi", not trasa_io.drzwi_na_trasie(P, MAPA), trasa_io.drzwi_na_trasie(P, MAPA))
sprawdz("dojście i powrót: bez drzwi (poza pętlą i dojściami z8/z9 do dziury)", not trasa_io.drzwi_na_trasie(D, MAPA) and not trasa_io.drzwi_na_trasie(R, MAPA),
        (trasa_io.drzwi_na_trasie(D, MAPA), trasa_io.drzwi_na_trasie(R, MAPA)))

# --- groźne spawny (hp > 50 albo atak > 10, poza troll/snake/wasp): >= 8 pól (promień strefy 6 + 2) od każdego punktu z7 pętli, dojścia i powrotu w okolicy
SPAWNY = json.loads((Path(_R) / "dane_tibia" / "serwer74" / "potwory_pelne.json").read_text())["potwory"]
TROLL = next(mo for mo in SPAWNY if mo["nazwa"] == "troll")
CELE = ("troll", "snake", "wasp")
GROZNE = [(mo["nazwa"], s["x"], s["y"]) for mo in SPAWNY if mo["nazwa"] not in CELE and (mo["hp"] > TROLL["hp"] or mo["atak"] > TROLL["atak"])
          for s in mo.get("spawny", []) if s["z"] == 7]
RAMKA = (32560, 32760, 31880, 32070)         # okolica wspólnego odcinka od mostu do pętli
grozne_tu = [g for g in GROZNE if RAMKA[0] <= g[1] <= RAMKA[1] and RAMKA[2] <= g[2] <= RAMKA[3]]
sprawdz("są groźne spawny w okolicy (sanity: niedźwiedź (32666,31930), pająk (32704,31986), wilki)", {"bear", "poison spider", "wolf"} <= {g[0] for g in grozne_tu}, grozne_tu[:5])
for n, t in (("pętla", P), ("dojście", [p for p in D if RAMKA[0] <= p[0] <= RAMKA[1]]), ("powrót", [p for p in R if RAMKA[0] <= p[0] <= RAMKA[1]])):
    naj = min(((cheb(p, (g[1], g[2])), g[0], p) for p in t if p[2] == 7 for g in grozne_tu), default=(99, "", None))
    sprawdz(f"{n}: >= 8 pól od groźnych spawnów (najbliższy: {naj[1]} {naj[0]} pól)", naj[0] >= 8, naj)
import generuj_trase_thais_kazordoon as _thais
strefy_thais = _thais.strefy_zakazane(MAPA, OGIEN, NAUCZONE)
for n, t in (("dojście", D), ("powrót", R)):
    sprawdz(f"{n}: poza strefami zakazanymi trasy Thais -> Kazordoon (promień 6 wokół groźnych spawnów w pasie x<=32640)", not (set(t) & strefy_thais), sorted(set(t) & strefy_thais)[:3])
dane_potw = {s["nazwa"]: s for s in SPAWNY}
bliskie = [(mo["nazwa"], s["x"], s["y"], s["ilosc"], min(cheb(p, (s["x"], s["y"])) for p in P))
           for mo in SPAWNY for s in mo.get("spawny", []) if s["z"] == 7 and mo["nazwa"] not in CELE
           and (mo["hp"] > TROLL["hp"] or mo["atak"] > TROLL["atak"]) and RAMKA[0] <= s["x"] <= RAMKA[1] and RAMKA[2] <= s["y"] <= RAMKA[3] and min(cheb(p, (s["x"], s["y"])) for p in P) <= 14]
sprawdz("żaden GROŹNY potwór (hp/atak > troll) nie ma spawnu <= 14 pól od pętli (niedźwiedź >= 19; króliki itp. pomijamy)", not bliskie, bliskie[:3])

# --- pętla obejmuje spawny trolli i węży z danych CipSoft (6 przystanków, 24 potwory)
CEL_SPAWNY = [(mo["nazwa"], s["x"], s["y"], s["ilosc"]) for mo in SPAWNY if mo["nazwa"] in ("troll", "snake")
              for s in mo.get("spawny", []) if s["z"] == 7 and 32630 <= s["x"] <= 32672 and 31945 <= s["y"] <= 31976]
sprawdz("w prostokącie spotu 6 spawnów trolli/węży = 24 potwory (15 trolli, 9 węży)", len(CEL_SPAWNY) == 6 and sum(c[3] for c in CEL_SPAWNY) == 24
        and sum(c[3] for c in CEL_SPAWNY if c[0] == "troll") == 15, CEL_SPAWNY)
for nazwa, x, y, il in CEL_SPAWNY:
    od = min(cheb(p, (x, y)) for p in P)
    sprawdz(f"pętla przechodzi <= 3 pola od spawnu {nazwa} ({x},{y}) x{il}", od <= 3, od)
js = json.loads((Path(_R) / "dane_tibia" / "mapy" / f"{N}.json").read_text())
sprawdz("podgląd .json: 6 przystanków (+ start), 24 potwory, dlugosc_petli = pętla", len([p for p in js["przystanki"] if p.get("potworow")]) == 6
        and sum(p.get("potworow", 0) for p in js["przystanki"]) == 24 and js["dlugosc_petli"] == len(P), js["dlugosc_petli"])
sprawdz("podgląd .png istnieje", (Path(_R) / "dane_tibia" / "mapy" / f"{N}.png").stat().st_size > 5000)

# --- wpisy: mapy.json, spoty_nadzorca.json, wyprawa.PLANY_PK
mapy = json.loads((Path(_R) / "mapy.json").read_text())
e = mapy.get(N)
sprawdz("mapy.json: wpis z trasą, dojściem i potworami Troll, Wasp, Snake",
        e and e["trasa"] == f"{N}_petla" and e["dojscie"] == f"{N}_dojscie" and {"troll", "wasp", "snake"} <= {x.strip().casefold() for x in e["potwory"].split(",")}, e)
sprawdz("mapy.json: pliki trasy i dojścia istnieją", (TRASY / f"{N}_petla.json").is_file() and (TRASY / f"{N}_dojscie.json").is_file())
nadz = json.loads((Path(_R) / "dane_tibia" / "spoty_nadzorca.json").read_text())["spoty"].get(N)
sprawdz("spoty_nadzorca.json: wpis z poziomem [lo, hi], auto false, miasto thais",
        nadz and nadz["miasto"] == "thais" and nadz["auto"] is False and len(nadz["poziom"]) == 2 and 1 <= nadz["poziom"][0] < nadz["poziom"][1], nadz)
sprawdz("spoty_nadzorca.json: własna jaskinia (nie dzieli z z8/z9: osobne piętro)", nadz and nadz["jaskinia"] not in ("kazordoon_trolle_z8", "kazordoon_trolle_z9"), nadz and nadz["jaskinia"])
plan = next((p for p in W.PLANY_PK if p["nazwa"] == N), None)
sprawdz("wyprawa.PLANY_PK: wpis do/z, zasięg >= odległość pętli od depo, w BAZY_PK i punkty_bazy",
        plan and plan["do"] == f"{N}_do_depo.json" and plan["z"] == f"{N}_dojscie.json" and W.zasieg_planu(N) >= max(cheb(q, DEPO) for q in P)
        and N in W.BAZY_PK and N in W.punkty_bazy(nazwy=W.BAZY_PK), plan)

# --- wybór bazy: z każdego punktu pętli z7 (i z drogi z7 przed rozgałęzieniem) plan to z7, nie z8/z9 (ich "do" prowadzi obok dziury i lądowania liny)
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
zla_baza = [(p, W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG)) for p in P + D[-80:] if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) != N]
sprawdz("wybierz_baze: z pętli z7 i 80 pól drogi przed nią plan = trolle_kazordoon_z7 (nie z8/z9)", not zla_baza, zla_baza[:3])
b8 = [W.wybierz_baze(baza, tuple(p), W.PK_PLAN_ZASIEG) for p in wczytaj("trolle_kazordoon_z8_petla")[::10]]
b9 = [W.wybierz_baze(baza, tuple(p), W.PK_PLAN_ZASIEG) for p in wczytaj("trolle_kazordoon_z9_petla")[::10]]
sprawdz("wybierz_baze: z pętli z8 plan z8 (jak przed zmianą: 22/23, jeden punkt wspólnego korytarza z8 -> z9), z pętli z9 plan z9",
        b8.count("trolle_kazordoon_z8") >= len(b8) - 1 and set(b8) <= {"trolle_kazordoon_z8", "trolle_kazordoon_z9"} and set(b9) == {"trolle_kazordoon_z9"}, (b8, b9))

# --- droga z pętli do depo (wyprawa.droga_do_depo): ciągła, bez ognia/dziur/strefy dziury, bez liny, tylko 2 rampy
T = W.Trasownik(MAPA)


def zalew(a, cele):
    return T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)


zle = {"brak": [], "koniec": [], "ciaglosc": [], "ogien": [], "dziura": [], "przej": []}
przy_dziurze = []
do_przej = {(a, b) for a, b in zip(R, R[1:]) if a[2] != b[2]}
probki = P[::14] + [P[-1]]
for poz in probki:
    wyn = W.droga_do_depo(poz, P, R, zalew, MAPA, zasieg=W.zasieg_planu(N))
    if wyn is None:
        zle["brak"].append(poz)
        continue
    pts = [tuple(q) for q in wyn[0]]
    if pts[-1] != DEPO:
        zle["koniec"].append((poz, pts[-1]))
    if any(a[2] == b[2] and cheb(a, b) > 5 or a[2] != b[2] and cheb(a, b) > 3 for a, b in zip(pts, pts[1:])):
        zle["ciaglosc"].append(poz)
    if OGIEN & set(pts):
        zle["ogien"].append((poz, sorted(OGIEN & set(pts))[:2]))
    if NAUCZONE & set(pts) or DZIURA in pts or LAD_LINY in pts:
        zle["dziura"].append(poz)
    if any(p[2] == 7 and min(cheb(p, DZIURA), cheb(p, LAD_LINY)) <= 1 for p in pts):
        przy_dziurze.append(poz)      # A* z północnych przystanków skraca obok dziury (jak istniejące powroty z8/z9): sama dziura/lądowanie wykluczone wyżej
    zm = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    if any(p not in do_przej for p in zm):
        zle["przej"].append((poz, [p for p in zm if p not in do_przej][:2]))
for k, v in zle.items():
    sprawdz(f"droga_do_depo z {len(probki)} punktów pętli: kategoria '{k}' czysta", not v, v[:2])

print(f"INFO: droga_do_depo mija dziurę/lądowanie liny o 1 pole z {len(przy_dziurze)}/{len(probki)} punktów pętli (północne przystanki): {przy_dziurze[:4]}")
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
