"""22.10: spoty trolle_kazordoon_z8 / z9: jedno wspólne dojście z depo THAIS (korekta Karola 22.10: "na trolle pod", nie przez miasto Kazordoon) (reguła Karola: trasy ze wspólnych odcinków,
bez dublowania dróg). Repo nie składa tras w locie, więc każdy spot ma własne `_dojscie` = wspólny odcinek + własna odnoga;
test pilnuje identycznego prefiksu, ciągłości, ognia, drzwi i kroków liną w powrocie. Dane rzeczywiste; nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import trasa_io

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test Kazordoonu")
    sys.exit(0)


def wczytaj(nazwa):
    return [tuple(int(v) for v in p) for p in trasa_io.wczytaj(nazwa)[0]]


DEPO = (32348, 32225, 7)          # depo Thais
FORK = (32647, 32003, 8)
LAD9 = (32648, 32004, 9)
LAND8 = (32663, 31962, 8)         # 24.10: lądowanie pod dziurą = koniec dojścia z8 = POLE LINY powrotu (musi zostać wolne)
STOI8 = (32663, 31961, 8)         # 24.10: start i koniec pętli z8: pole OBOK pola liny
DRZWI8 = (32657, 31965, 8)
D8, D9 = wczytaj("trolle_kazordoon_z8_dojscie"), wczytaj("trolle_kazordoon_z9_dojscie")
P8, P9 = wczytaj("trolle_kazordoon_z8_petla"), wczytaj("trolle_kazordoon_z9_petla")
R8, R9 = wczytaj("trolle_kazordoon_z8_do_depo"), wczytaj("trolle_kazordoon_z9_do_depo")
MAPA = _mapa.Mapa()

# --- wspólny prefiks dojść
sprawdz("dojścia zaczynają w depo Thais", D8[0] == DEPO and D9[0] == DEPO, (D8[0], D9[0]))
sprawdz("24.10: dojście z8 kończy na lądowaniu pod dziurą (wejście do pętli), nie na rozwidleniu", D8[-1] == LAND8 and FORK not in D8, D8[-1])
sprawdz("wspólny prefiks dojść identyczny (z8 = wspólny odcinek, z9 = ten sam + odnoga)", D9[:len(D8)] == D8, "prefiksy różne")
odn = D9[len(D8):]
sprawdz("odnoga z9 = dotychczasowy odcinek dziura -> drzwi z8 -> rozwidlenie + schody z8 + lądowanie z9 (BEZ ZMIAN)",
        odn[-2:] == [(32648, 32003, 8), LAD9] and DRZWI8 in odn and FORK in odn and odn.index(DRZWI8) < odn.index(FORK) and odn[-3] == FORK,
        (odn[:2], odn[-3:]))
sprawdz("odnoga z9: z lądowania pod dziurą idzie obok pola liny, nie po nim", LAND8 not in odn, "")
sprawdz("wspólny odcinek >= 300 pól", len(D8) >= 300, len(D8))

# --- pętle zaczynają tam, gdzie kończy dojście
sprawdz("24.10: pętla z8 zaczyna i kończy się przy dziurze, na polu obok pola liny", P8[0] == STOI8 and P8[-1] == STOI8, (P8[0], P8[-1]))
sprawdz("24.10: koniec dojścia z8 sąsiaduje z początkiem pętli (jedno pole)", max(abs(D8[-1][0] - P8[0][0]), abs(D8[-1][1] - P8[0][1])) == 1 and D8[-1][2] == P8[0][2], (D8[-1], P8[0]))
sprawdz("24.10: pętla z8 nie wchodzi na pole liny (lina wymaga wolnego pola)", LAND8 not in P8, "")
sprawdz("pętla z9 startuje przy lądowaniu", P9[0][2] == 9 and max(abs(P9[0][0] - LAD9[0]), abs(P9[0][1] - LAD9[1])) <= 3, P9[0])
sprawdz("pętle zamknięte na jednym piętrze", {p[2] for p in P8} == {8} and {p[2] for p in P9} == {9})
# kieszeń z trollami przy dziurze (spawn (32658,31960)) i dotychczasowa pętla (rozwidlenie) w jednej pętli
sprawdz("24.10: pętla z8 obejmuje kieszeń z trollami (spawn (32658,31960) w odległości <= 1)",
        min(max(abs(p[0] - 32658), abs(p[1] - 31960)) for p in P8) <= 1, "")
sprawdz("24.10: pętla z8 obejmuje dotychczasową pętlę na południu (wejście za drzwiami, spawny trolli aż do y>=32000), ale NIE rozwidlenie przy schodach na z9",
        (32657, 31966, 8) in P8 and any(p[1] >= 32000 for p in P8) and FORK not in P8, "")
ix = [i for i, p in enumerate(P8) if p == DRZWI8]
sprawdz("24.10: pętla z8 przechodzi drzwi dokładnie 2 razy (jedno wejście: tam i z powrotem)", len(ix) == 2, ix)
sprawdz("24.10: drzwi pętli przekraczane prostopadle (w osi x, bez skosu)",
        all(P8[i - 1][0] == P8[i][0] == P8[i + 1][0] for i in ix if 0 < i < len(P8) - 1) and len(ix) == 2, ix)
if len(ix) == 2:
    cala = P8[ix[0]:ix[1] + 1]
    # wyprawa za drzwi (tam) i z powrotem tą samą drogą: korytarz + obieg dotychczasowej pętli; poza nim kieszeń to wyłącznie przed pierwszymi drzwiami
    sprawdz("24.10: kieszeń przed drzwiami i za drzwiami rozdzielone (kieszeń na północ od drzwi, pętla na południe)",
            all(p[1] < DRZWI8[1] for p in P8[:ix[0]]) and all(p[1] < DRZWI8[1] for p in P8[ix[1] + 1:]) and all(p[1] > DRZWI8[1] for p in cala[1:-1]),
            (P8[:ix[0]][-1], cala[1], cala[-2]))
# 24.10 (incydent 08:51): schody z8 -> z9 (32648,32003) prowadzą na bardzo niebezpieczne z9; pętla z8 trzyma 2 pola odstępu, dojście i powrót z8 nie stają na nich
SCHODY8 = (32648, 32003, 8)
sprawdz("24.10: pętla z8 nie wchodzi w bufor 1 wokół schodów na z9", all(max(abs(p[0] - SCHODY8[0]), abs(p[1] - SCHODY8[1])) > 1 for p in P8), [p for p in P8 if max(abs(p[0] - SCHODY8[0]), abs(p[1] - SCHODY8[1])) <= 1][:3])
sprawdz("24.10: dojście z8 i powrót z8 nie stają na schodach na z9", SCHODY8 not in D8 and SCHODY8 not in R8, "")
_dz = json.loads((Path(_R) / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])
sprawdz("24.10: schody na z9 (32648,32003,8) są w dziury_nauczone.json (ściana dla A* i kroków bota; trasa celowo schodząca nimi, czyli z9, przechodzi)", list(SCHODY8) in _dz, "")
pow_ = {}
for p in P8[:-1]:
    pow_[p] = pow_.get(p, 0) + 1
dubl = {p for p, n in pow_.items() if n > 1}
sprawdz("24.10: kieszeń (ślepa uliczka) cofa się tylko na kilku polach: <= 8 pól na północ od drzwi i na nich odwiedzanych dwa razy, drzwi i pole przed nimi wśród nich",
        len({p for p in dubl if p[1] <= DRZWI8[1]}) <= 8 and {(32657, 31964, 8), DRZWI8} <= dubl, sorted(p for p in dubl if p[1] <= DRZWI8[1])[:9])
# 24.10 12:51: nowy ogień z8 (epizody (32643,31971), stałe (32650,31971..72)) z buforem 1 przecina korytarz y=31973 i dotychczasowy OBIEG zamienia się w wyjście i powrót
# jedną drogą na zachód (generator trzyma bufor jako ścianę): pętla ma ~307 pól zamiast ~223 (kieszeń ~21 + obieg ~283 w tym dublowanie)
sprawdz("24.10: pętla z8 bez rozdęcia (obieg z odnogami po ogniu + kieszeń ~21 + drzwi: <= 330 pól)", len(P8) <= 330, len(P8))
sprawdz("24.10: wejście do dotychczasowej pętli bez korytarza w obie strony (pole za drzwiami jest na obiegu)", (32657, 31966, 8) in P8, "")


def ciagla(trasa):
    """Kolejne punkty tego samego piętra są w odległości <= 1 (Chebyshev); zmiana piętra o <= 2 pola."""
    for a, b in zip(trasa, trasa[1:]):
        d = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
        if d > (2 if a[2] != b[2] else 1):
            return (a, b)
    return None


for n, t in (("dojście z8", D8), ("dojście z9", D9), ("pętla z8", P8), ("pętla z9", P9), ("powrót z8", R8), ("powrót z9", R9)):
    sprawdz(f"{n}: ciągłość", ciagla(t) is None, ciagla(t))

# --- ogień: żaden punkt nowych tras nie leży na znanym ogniu ani obok
OGIEN = set()
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((Path(_R) / "trasy" / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
# 24.10 12:51: WYJĄTEK od bufora: dziura z7 (32663,31962), lądowanie liny (32663,31963) i pole przed nim (32663,31964) leżą w buforze ognia (32664,31963,z7); bez nich wejście do
# dziury nie istnieje. Tylko te 3 pola i tylko na z7; samo pole ognia i reszta trasy nadal omijane.
WEJSCIE = {(32663, 31962, 7), (32663, 31963, 7), (32663, 31964, 7)}
sprawdz("24.10: wyjątek od bufora ognia to dokładnie wejście do dziury (ogień (32664,31963,z7) leży obok niego, nie na nim)",
        (32664, 31963, 7) in OGIEN and not (WEJSCIE & OGIEN), WEJSCIE & OGIEN)
for n, t in (("dojście", D9), ("dojście z8", D8), ("pętla z8", P8), ("pętla z9", P9), ("powrót z8", R8), ("powrót z9", R9)):
    zle = [p for p in t if p not in WEJSCIE and any((p[0] + dx, p[1] + dy, p[2]) in OGIEN for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    sprawdz(f"{n}: bez ognia (bufor 1, poza wejściem do dziury)", not zle, zle[:3])
    sprawdz(f"{n}: nigdzie na polu ognia", not [p for p in t if p in OGIEN], [p for p in t if p in OGIEN][:3])
# 24.10 12:51 (odchyd, 10 min na dojściu): (32659,31966,z7) mapa uważa za drzwi, ale w grze się NIE otwierają (6 prób Use 12:50, też 09:56 i 12:31); trasa idzie dookoła przez (32661,31966)
NIE_DRZWI7 = (32659, 31966, 7)
OBEJSCIE = (32661, 31966, 7)
for n, t in (("dojście z8", D8), ("dojście z9", D9), ("powrót z8", R8), ("powrót z9", R9)):
    sprawdz(f"24.10: {n} nie wchodzi na (32659,31966,z7) (to nie drzwi) i idzie przez obejście (32661,31966)", NIE_DRZWI7 not in t and OBEJSCIE in t, (NIE_DRZWI7 in t, OBEJSCIE in t))
sprawdz("24.10: dojście z8: ostatnie pola na z7 to (32663,31965) -> (32663,31964) -> (32663,31963) -> dziura (32663,31962), potem z8",
        D8[-5:] == [(32663, 31965, 7), (32663, 31964, 7), (32663, 31963, 7), (32663, 31962, 7), (32663, 31962, 8)], D8[-6:])

# --- drzwi: dokładnie 2 w dojściu, rozpoznane przez mechanizm trasy (DRZWI_TRASA)
DRZWI = {(32657, 31965, 8)}                # od 24.10 12:51 bez (32659,31966,z7): to nie są drzwi trasy
got = {x["pole"] for x in trasa_io.drzwi_na_trasie(D8, MAPA)}
sprawdz("dojście z8 (od 24.10 kończy pod dziurą; 12:51 bez drzwi z7, które się nie otwierają): żadnych drzwi", got == set(), got)
got = {x["pole"] for x in trasa_io.drzwi_na_trasie(D9, MAPA)}
sprawdz("dojście z9: drzwi rozpoznane = tylko drzwi z8", got == {DRZWI8}, got)
got = trasa_io.drzwi_na_trasie(P8, MAPA)
sprawdz("pętla z8: drzwi z8 rozpoznane przez mechanizm trasy (pierwsze przejście; kolejne przejście tych samych drzwi pętla powtarza)",
        {x["pole"] for x in got} == {DRZWI8} and tuple(got[0]["kier"]) == (0, 1), got)
for n, t in (("powrót z8", R8), ("powrót z9", R9)):
    got = {x["pole"] for x in trasa_io.drzwi_na_trasie(t, MAPA)}
    sprawdz(f"{n}: drzwi powrotu = tylko drzwi z8", got == DRZWI, got)

# --- 22.10: droga z Thais: bez grobli z6 z dwarfami i bez miasta Kazordoon, głównie po szarej drodze, jedna lina w powrocie
for n, t in (("dojście z8", D8), ("dojście z9", D9), ("powrót z8", R8), ("powrót z9", R9)):
    grobla = [p for p in t if p[2] == 6 and 32610 <= p[0] <= 32625 and 31960 <= p[1] <= 31975]
    sprawdz(f"{n}: nie wchodzi na groblę z6 (dwarfy) i do miasta Kazordoon (z9+ poza jaskinią)", not grobla, grobla[:3])
    pow_ = [p for p in t if p[2] in (6, 7)]
    dr = sum(1 for p in pow_ if MAPA.pole(*p)[1] == 129)
    sprawdz(f"{n}: >= 60% pól powierzchni po szarej drodze", dr * 100 >= 60 * len(pow_), f"{dr}/{len(pow_)}")
MOST = [(32548, 32076, 7), (32549, 32076, 6), (32553, 32076, 6), (32554, 32076, 6), (32555, 32076, 7)]
sprawdz("dojście: przechodzi przez most Thais (pomost z6 32549..32553)", all(p in D8 for p in MOST), [p for p in MOST if p not in D8])
sprawdz("dojście z8: przejścia pięter to 3 (rampa, rampa, dziura z7)", sum(1 for a, b in zip(D8, D8[1:]) if a[2] != b[2]) == 3)

# --- powrót: jedna lina (z8->z7), start/koniec, wspólny sufiks
sprawdz("powrót z8 kończy w depo", R8[-1] == DEPO, R8[-1])
sprawdz("powrót z9 kończy w depo", R9[-1] == DEPO, R9[-1])
sprawdz("powrót z8 startuje na rozwidleniu", R8[0] == FORK, R8[0])
sprawdz("powrót z9 startuje na lądowaniu z9", R9[0] == LAD9, R9[0])
k = R9.index((32648, 32004, 8)) if (32648, 32004, 8) in R9 else -1
sprawdz("powrót z9 wchodzi na z8 schodami", k > 0, k)
sprawdz("wspólny sufiks powrotów (z9 po wyjściu na z8 = powrót z8)", k > 0 and R9[k + 1:][-len(R8) + 1:] == R8[1:] if k > 0 else False, "sufiksy różne")
for lina, stoi, ladowanie in (((32663, 31962, 8), (32663, 31961, 8), (32663, 31963, 7)),):
    j = R8.index(stoi) if stoi in R8 else -1
    sprawdz(f"lina {lina[:2]}: stoi obok pola liny, następny punkt = lądowanie",
            j >= 0 and R8[j + 1] == ladowanie and stoi != lina and lina not in R8, (stoi, R8[j + 1] if j >= 0 else None))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
