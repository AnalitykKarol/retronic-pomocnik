"""16.10: wyprawa do depo Edron (PLANY_PK) z DOWOLNEGO miejsca spotu: najkrótsza droga z bieżącej pozycji
(wyprawa.droga_do_depo), nie ślepo nagranie "do" od początku i nie tylko w zasięgu 80 pól na tym samym piętrze.
Dane rzeczywiste: trasy/edron_nowy_spot.json (pętla łowiska), edron_do_depo.json, prawdziwa mapa. Nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import wypad
import wyprawa as W

TRASY = Path(_R) / "trasy"
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test drogi do depo Edron")
    sys.exit(0)

MAPA = _mapa.Mapa()
L = [tuple(int(v) for v in p) for p in json.loads((TRASY / "edron_nowy_spot.json").read_text())]
D = [tuple(int(v) for v in p) for p in json.loads((TRASY / "edron_do_depo.json").read_text())]
DEPO = (33173, 31796, 8)
T = W.Trasownik(MAPA)


def zalew(a, cele):
    return T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)


def ciagla(pts, krok=5):
    """Kolejne punkty: na piętrze <= krok pól, przy zmianie piętra <= 3 pola."""
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > krok:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


def baseline_do(poz):
    """Prosta alternatywa 1 (stare zachowanie, ale z dojściem): marsz po piętrze do któregokolwiek punktu 'do' + jego reszta."""
    z = zalew(poz, [q for q in D if q[2] == poz[2]])
    k = [W.koszt_punktow(z[q] + D[j + 1:]) for j, q in enumerate(D) if q in z]
    return min(k) if k else None


def baseline_petla_do_przodu(i):
    """Prosta alternatywa 2: z węzła pętli i do przodu do jej końca (z8, start), stamtąd marsz do 'do' i trasa 'do'."""
    pts = L[i:]
    z = zalew(pts[-1], [q for q in D if q[2] == pts[-1][2]])
    k = [W.koszt_punktow(pts + z[q][1:] + D[j + 1:]) for j, q in enumerate(D) if q in z]
    return min(k) if k else None


# 1. plan powstaje, jest ciągły, kończy się w depo i nie jest dłuższy niż prosta alternatywa (dane rzeczywiste)
pozycje = [("z8 start nowego spotu", L[0], 0), ("z8 blisko startu", (33079, 31740, 8), None),
           ("z9 tuż po zejściu", L[4], 4), ("z10 zaraz po zejściu", L[7], 7), ("z9 środek", L[40], 40),
           ("z10 środek (lina w górę niedaleko)", L[67], 67), ("z9 daleko od wyjścia", L[63], 63),
           ("z10 po lewej stronie pętli", L[126], 126), ("z9 pod koniec pętli", L[190], 190),
           ("z8 koniec pętli", L[-2], len(L) - 2), ("z8 poza pętlą, kilka pól od niej", (33090, 31745, 8), None),
           ("z9 dwa pola od trasy", (L[40][0] - 1, L[40][1] - 2, 9), None)]
baza_do = W.wypad.sprawdz_plan(W.wypad.zbuduj_etapy(D, MAPA), MAPA)        # uwagi nagrania 'do' (nie od tej zmiany)
tmax = 0.0
for opis, poz, i in pozycje:
    t0 = time.time()
    r = W.droga_do_depo(poz, L, D, zalew, MAPA)
    dt = time.time() - t0
    tmax = max(tmax, dt)
    if r is None:
        sprawdz(f"1 {opis} {poz}: plan powstaje", False, "brak drogi")
        continue
    pts, koszt, kom = r
    et = wypad.zbuduj_etapy(pts, MAPA)
    nowe = [b for b in wypad.sprawdz_plan(et, MAPA) if b not in baza_do and "(33167, 31811, 7)" not in b]
    sprawdz(f"1 {opis} {poz}: ciągły, od pozycji do depo, etapy bez nowych uwag",
            pts[0] == poz and pts[-1] == DEPO and ciagla(pts) is None and not nowe, f"{ciagla(pts)} {nowe[:2]} {pts[-1]}")
    alt = [a for a in (baseline_do(poz), baseline_petla_do_przodu(i) if i is not None else None) if a is not None]
    sprawdz(f"1 {opis}: koszt {koszt} <= prosta alternatywa {min(alt) if alt else None} ({kom[:48]})",
            not alt or koszt <= min(alt), f"{koszt} > {alt}")
sprawdz(f"1z czas liczenia planu <= {W.DEPO_LIMIT_S + 4:.0f} s (najdłuższy {tmax:.1f} s)", tmax <= W.DEPO_LIMIT_S + 4)

# 2. odwrotne przejście pięter: wstecz po pętli etapy to LINA/DZIURA ustawiona przy polu z mapy (nie nagranie w złą stronę)
pts, koszt, kom = W.droga_do_depo(L[7], L, D, zalew, MAPA)
et = wypad.zbuduj_etapy(pts, MAPA)
przejscia = [e for e in et if e["typ"] in ("LINA", "DZIURA")]
sprawdz("2a z10 tuż po zejściu: wstecz po pętli, pierwsze przejście to lina/schody w górę z pola potwierdzonego mapą",
        "wstecz" in kom and przejscia and przejscia[0]["typ"] == "LINA" and wypad.cheb(przejscia[0]["stoi"], przejscia[0]["cel"]) <= 1,
        f"{kom} {przejscia[:1]}")
sprawdz("2b lina z mapy: pole liny to pewny kandydat pietra.kandydaci",
        przejscia and any(k["pewne"] and tuple(k["pole"]) == tuple(przejscia[0]["cel"])
                          for k in __import__("pietra").kandydaci(MAPA, przejscia[0]["stoi"], przejscia[0]["ladunek"])),
        f"{przejscia[:1]}")
sprawdz("2c bez mapy odwrotne przejście jest niemożliwe (None), zostaje marsz do przodu",
        W._przejscie_odwrotne(None, L[4], L[3]) is None)
r_bez = W.droga_do_depo(L[7], L, D, zalew, None)
sprawdz("2d bez mapy plan z z10 idzie tylko do przodu po pętli (bez cofania przez przejścia)",
        r_bez is not None and "wstecz" not in r_bez[2] and r_bez[0][-1] == DEPO, f"{r_bez and r_bez[2]}")

# 3. daleko od depo (inne miasto) i inne piętro bez połączenia: brak planu, nie zgadywanie
sprawdz("3a Thais (daleko od depo Edron): brak planu", W.droga_do_depo((32369, 32241, 7), L, D, zalew, MAPA) is None)
sprawdz("3b z5 nad spotem (brak węzłów na tym piętrze): brak planu", W.droga_do_depo((33090, 31745, 5), L, D, zalew, MAPA) is None)
sprawdz("3c pusta pętla: dalej działa marsz do trasy 'do' z z8",
        (lambda r: r is not None and r[0][-1] == DEPO and r[0][0] == (33090, 31745, 8))(
            W.droga_do_depo((33090, 31745, 8), [], D, zalew, MAPA)))

# 4. integracja: Wyprawa._start_wyprawa z dowolnego miejsca spotu


class KonfW:
    WYPRAWA_AKTYWNA = 1
    WYPRAWA_MAX_CZAS_S = 1800
    WYPRAWA_MAX_KROKOW = 6000
    WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CO_MIN = 20
    WYPRAWA_PO_DEPO_S = 900
    WYPRAWA_DEPO_POWROT = 0
    WYPRAWA_TYLKO_DEPO = 1
    DEPO_EDRON_OBSZAR = 0        # 24.10: stare stanowisko; obszar ma test_depo_edron_obszar


class CBW:
    mapa = MAPA

    def __init__(c, poz, punkty):
        c.t = 0.0
        c.wypad_aktywny = False
        c.poz = poz
        c.punkty = list(punkty)
        c.stan = None
        c.postac = types.SimpleNamespace(pozycja=lambda: c.poz)

    def zegar(c):
        return c.t

    def gracz(c):
        return {"proc": 60.0}

    def _wypad_reset_klik(c):
        pass

    def droga(c, *a, **k):
        return []

    def pauza(c, *a):
        pass


class OpsW:
    def wiadomosci(o):
        return []


def nowa(poz, punkty=L, nr=[0]):
    nr[0] += 1
    cb = CBW(poz, punkty)
    logi = []
    w = W.Wyprawa(cb, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / f"st{nr[0]}.json",
                  plik_sklepow=TMP / "sk.json", plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{nr[0]}",
                  czas=lambda: 5_000_000.0)
    return w, cb, logi


dane = {"powody": ["glod"], "zapas": 0, "blanki": None, "zloto": 100, "cap": 100, "hp": 90, "pochodnie": None, "depo": True}
POZ_Z9 = (33098, 31709, 9)          # piętro 9 środka pętli: stara reguła (to samo piętro, 80 pól od punktu 'do') nie startowała
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
sprawdz("4a stara reguła wybierz_baze nie wybiera planu z z9 (to był błąd)", W.wybierz_baze(baza, POZ_Z9, W.PK_PLAN_ZASIEG) is None)
for opis, poz in [("z9 środek pętli", POZ_Z9), ("z10 w pętli", L[67]), ("z8 start nowego spotu", L[0]), ("z8 koniec pętli", L[-2])]:
    w, cb, logi = nowa(poz)
    wynik = w._start_wyprawa("depo:glod", dane, 0.0)
    legs = w.w["legs"][0] if w.w else []
    idz = [e for e in legs if e["typ"] == "IDZ"]
    sprawdz(f"4b {opis}: wyprawa do depo startuje, plan 'edron', pierwszy punkt = pozycja, cel depo",
            wynik is True and w.w["baza"] == "edron" and idz and tuple(idz[0]["punkty"][0]) == poz
            and tuple(w.w["stops"][0]["stoi"]) == DEPO and tuple(idz[-1]["punkty"][-1]) == DEPO,
            f"{wynik} {logi[-2:]}")
    sprawdz(f"4c {opis}: stan zapisuje z_poz, potrzeby bez zmian (depo=True)",
            w._stan_czytaj().get("z_poz") == list(poz) and w.w["potrzeby"] == {"depo": True})
w, cb, logi = nowa(POZ_Z9)
w._start_wyprawa("depo:glod", dane, 0.0)
sprawdz("4d droga zalogowana (koszt i opis)", any("Wyprawa: depo: droga z" in l for l in logi), f"{logi[-3:]}")
sprawdz("4e nagrane 'do' nie zaczyna się ślepo od indeksu 0: plan nie zawiera punktu startowego trasy 'do' (33110,31774,8)",
        D[0] not in [tuple(p) for e in w.w["legs"][0] if e["typ"] == "IDZ" for p in e["punkty"]]
        and w.w["legs"][0][-1]["punkty"][-1] == DEPO)

# 5. bez zmian: zwykła wyprawa po zapasy i inne bazy; za daleko od depo; brak mapy -> stara droga
w, cb, logi = nowa(POZ_Z9)
d_zw = dict(dane, depo=False, pochodnie=0)
sprawdz("5a zwykła wyprawa po zapasy (nie depo) z z9 Edron nadal nie rusza (poza planami BAZY)",
        w._start_wyprawa("glod", d_zw, 0.0) is False and w.w is None and w.nast_wyprawa > 0, f"{logi[-2:]}")
w, cb, logi = nowa((30000, 30000, 7))
sprawdz("5b depo spoza wszystkich planów i 200 pól od depo Edron: nie rusza, jak dotąd",
        w._start_wyprawa("depo:glod", dane, 0.0) is False and w.w is None, f"{logi[-2:]}")
sprawdz("5c wybierz_baze nadal działa jak dawniej: 80 pól na tym samym piętrze",
        W.wybierz_baze(baza, (33117, 31775, 8), 80) == "edron" and W.wybierz_baze(baza, (33117, 31775, 5), 80) is None)
w, cb, logi = nowa((33117, 31775, 8))
cb.mapa = None
sprawdz("5d bez mapy: start jak dawniej (trasa 'do' od początku), bez wyjątku",
        w._start_wyprawa("depo:glod", dane, 0.0) in (True, False))
w, cb, logi = nowa((33117, 31775, 8))
w._start_wyprawa("depo:glod", dane, 0.0)
sprawdz("5e WYPRAWA_TYLKO_DEPO: dojście kończy STOP + powiadomienie, bez powrotu",
        w.w is not None and w._tryb_depo() and not int(w._kw("WYPRAWA_DEPO_POWROT")))

# 6. ucieczka PK (start_pk) też liczy drogę z bieżącego miejsca (z9), a powrót po karencji bez zmian
w, cb, logi = nowa(POZ_Z9)
sprawdz("6a start_pk('ucieczka') z z9 środka pętli buduje plan do depo z pozycji",
        w.start_pk("ucieczka", 0.0) and w.w["potrzeby"] == {"depo": True, "pk": "ucieczka"}
        and tuple(w.w["legs"][0][0]["punkty"][0]) == POZ_Z9, f"{logi[-3:]}")
w._zakoncz_depo("depo", "ok")
cb.poz = DEPO
sprawdz("6b start_pk('powrot') z depo: trasa nagrana depo -> łowisko jak dawniej (cel (33117,31775,8))",
        w.start_pk("powrot", 10.0, baza="edron") and tuple(w.w["stops"][0]["stoi"]) == (33117, 31775, 8), f"{logi[-2:]}")

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
