#!/usr/bin/env python3
"""Droga piesza depo Thais <-> depo Kazordoon, z mapy klienta (22.10, OFFLINE, nic nie wysyła do gry):

  python3 -I generuj_trase_thais_kazordoon.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Cel: przenoszenie postaci na nowe spoty trolli pod Kazordoonem (trolle_kazordoon_z8/z9) "z buta" z Thais (decyzja Karola 22.10:
wychodzimy z Thais na północ, droga, jedno przejście przez most). Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  thais_kazordoon_tam              depo Thais (32348,32225,z7) -> depo Kazordoon (32598,31959,z11)        LINA na z7 (32613,31920)
  thais_kazordoon_tam_bez_liny     to samo bez liny: obchodzi górę od północy (3 drzwi, ok. +310 pól)       zapasowa
  thais_kazordoon_powrot           depo Kazordoon -> depo Thais: jawnie, NIE odwrócone "tam" (dziura w dół zamiast liny)
  thais_kazordoon.png, thais_kazordoon_most.png, thais_kazordoon_kaz.png (+ thais_kazordoon.json z danymi)

Metoda jak generuj_trasy_kazordoon_trolle.py (Planista: punkty kontrolne wpisane na sztywno, odcinki liczy A* po mapie piętra;
KAŻDE przejście pięter sprawdza pietra.kandydaci - musi dać "pewne" z polem przejścia = nasze T). Część Kazordoon (od schodów z6 przy
moście górskim do depo i od depo do z7) to DOKŁADNIE ten sam ciąg przejść co POWROT_Z8 / WSPOLNA w tamtym generatorze (jedno źródło
prawdy o wejściu do miasta: te same pola T i L). Ogień (trasy/ogien_*.json + bufor 1) i dziury nauczone = ściana.

MOST Thais: jedyne przejście przez wodę (Thais i wschodni brzeg to dwie osobne składowe z7). To POMOST NA z6 nad wodą z7
(32549..32553, 32076|32077): z7 (32548,y) i (32554,y) mają flagę 2 i kolor 210 (rampy), pomost na z6 jest chodliwy (kolor 129).
Wejście: z7 (32547,32076) -> T (32548,32076,z7) -> L (32549,32076,z6); zejście: T (32554,32076,z6) -> L (32555,32076,z7).
ZAŁOŻENIE (nie zmierzone w grze): rampa działa jak schody 210/210 na obu piętrach (pole lądowania = chodliwe pole obok, jak w
Kazordoonie: (32609,31963,z6)->(32608,31963,z7)). Wiersz 32077 jest równoległy (most ma 2 pola szerokości).
"""
import argparse
import heapq
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import pietra  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
from generuj_trasy_edron_z9z import ogien_pola  # noqa: E402
from spot_lib import chodliwe  # noqa: E402

NAZWA = "thais_kazordoon"
DEPO_THAIS = (32348, 32225, 7)          # depo Thais (start thais_pn_z8_dojscie, S7 generuj_trasy_thais_pn.py, serwis_thais.json)
BRAMA = (32367, 32179, 7)               # brama północna Thais: droga 4-polowa x 32367..32370 w murze y=32179 (mapa)
PN_DROGA = (32367, 32158, 7)            # droga na północ za bramą; prefiks 91 pól wspólny z thais_pn_z8_dojscie.json
DEPO_KAZ = (32598, 31959, 11)           # depo Kazordoon (jak w generuj_trasy_kazordoon_trolle.py); DO POTWIERDZENIA w grze
MOST_W = (32547, 32076, 7)              # pole przed rampą po stronie Thais
MOST_E = (32555, 32076, 7)              # pole po rampie po stronie wschodniej
STREFA = 6                              # promień strefy "groźniejszy niż troll" (jak Thais północ / Kazordoon z9)
PROMIEN_RAPORTU = 12                    # raport: spawny w tym promieniu od trasy
# drzwi na trasach (pola, które mapa uważa za ścianę, trasa przekracza je prostopadle; bot otwiera jak nagrane drzwi)
DRZWI = ((32611, 31921, 6), (32596, 31879, 7), (32586, 31911, 7), (32591, 31901, 8),
         (32659, 31966, 7), (32657, 31965, 8))      # ostatnie dwa: wejście do jaskini trolli pod Kazordoonem (jak w generuj_trasy_kazordoon_trolle.py)
ROZWIDLENIE = (32647, 32003, 8)         # koniec dojścia do trolli = start pętli z8 (jedno źródło prawdy; importuje je generuj_trasy_kazordoon_trolle.py)
DZIURA_TROLLE = (32663, 31962, 7)       # dziura z7 -> z8 do jaskini trolli (pod Kazordoonem)
# DROGA: 22.10 Karol "czemu nie idzie drogą": A* z kosztem terenu. Kolor 129 (szary, droga/ścieżka na minimapie Tibii) kosztuje 1, trawa i inny
# teren MNOZ_TEREN razy więcej, kolor 40 (woda płytka/brzeg, chodliwy w mapie, ale to nie droga) MNOZ_WODA. Tylko piętra z6/z7 (powierzchnia);
# jaskinie (z8+) liczone jak dotąd (koszt jednakowy). Skos kosztuje 3 (jak cavebot i mapa.droga), prosty 1.
KOLOR_DROGI = 129
MNOZ_TEREN = 4
MNOZ_WODA = 8
PIETRA_POWIERZCHNI = (6, 7)

# Wejście do miasta od z7 (32608,31963) = ogon POWROT_Z8 z generuj_trasy_kazordoon_trolle.py (lina w górę + schody w dół).
TAM_LINA = (
    ("lina", (32613, 31920, 7), (32613, 31921, 7), (32613, 31922, 6)),   # lina w górę z7->z6 pod dziurą (32613,31920,z6); lądowanie NIESPRAWDZONE
    ("przejscie", (32602, 31923, 6), (32603, 31923, 7)),                 # schody w dół z6 -> z7
    ("przejscie", (32602, 31923, 7), (32602, 31923, 8)),                 # dziura w dół z7 -> z8
    ("przejscie", (32613, 31921, 8), (32614, 31921, 9)),                 # schody w dół z8 -> z9
    ("przejscie", (32605, 31920, 9), (32604, 31920, 10)),                # z9 -> z10
    ("przejscie", (32613, 31925, 10), (32614, 31925, 11)),               # z10 -> z11
    ("do", DEPO_KAZ),
)
# Bez liny: obejście góry od północy po z7 (3 drzwi), z6 (32557,31924)..(32566,31940), z8 (32588,31908), potem te same schody w dół.
TAM_BEZ_LINY = (
    ("drzwi", (32596, 31879, 7), (-1, 0)),                               # drzwi z7 na północy góry (idziemy na zachód)
    ("przejscie", (32556, 31923, 7), (32557, 31924, 6)),                 # schody w górę z7 -> z6
    ("przejscie", (32567, 31940, 6), (32567, 31940, 7)),                 # schody w dół z6 -> z7
    ("drzwi", (32586, 31911, 7), (1, 0)),                                # drzwi z7 (na wschód)
    ("przejscie", (32588, 31908, 7), (32588, 31908, 8)),                 # z7 -> z8
    ("drzwi", (32591, 31901, 8), (1, 0)),                                # drzwi z8 (na wschód)
    ("przejscie", (32613, 31921, 8), (32614, 31921, 9)),
    ("przejscie", (32605, 31920, 9), (32604, 31920, 10)),
    ("przejscie", (32613, 31925, 10), (32614, 31925, 11)),
    ("do", DEPO_KAZ),
)
THAIS_MOST = (                                                           # wspólny początek wszystkich tras: depo Thais -> brama -> droga -> most -> wschodni brzeg
    ("start", DEPO_THAIS),
    ("do", BRAMA),
    ("do", PN_DROGA),
    ("do", MOST_W),
    ("przejscie", (32548, 32076, 7), (32549, 32076, 6)),                 # rampa w górę na pomost (z7 -> z6)
    ("do", (32553, 32076, 6)),                                           # POMOST z6 (32549..32553)
    ("przejscie", (32554, 32076, 6), (32555, 32076, 7)),                 # rampa w dół z pomostu (z6 -> z7)
)
# DOJŚCIE DO TROLLI (22.10, korekta Karola "chciałem na trolle trochę pod"): z depo Thais po powierzchni z7 (bez grobli z6 i miasta Kazordoon)
# do dziury (32663,31962,z7), kieszeń z8, drzwi, rozwidlenie. Importuje je generuj_trasy_kazordoon_trolle.py jako WSPÓLNY odcinek obu spotów.
THAIS_DO_TROLLI = THAIS_MOST + (
    ("drzwi", (32659, 31966, 7), (0, -1)),                               # drzwi z7 (na północ) przed dziurą
    ("przejscie", DZIURA_TROLLE, (32663, 31962, 8)),                     # dziura w dół z7 -> z8 (ŁOPATA, jeśli zasypana)
    ("drzwi", (32657, 31965, 8), (0, 1)),                                # drzwi z8
    ("do", ROZWIDLENIE),
)
# Powrót z rozwidlenia do depo Thais (jawnie, NIE odwrócone dojście): lina z dziury, drzwi, powierzchnia z7 -> most -> brama -> depo.
THAIS_POWROT_KONIEC = (                                                  # od wschodniego brzegu mostu do depo Thais (wspólny ogon powrotów)
    ("przejscie", (32554, 32076, 7), (32553, 32076, 6)),                 # rampa w górę na pomost od wschodu
    ("do", (32549, 32076, 6)),
    ("przejscie", (32548, 32076, 6), (32547, 32076, 7)),                 # rampa w dół, zachodni brzeg (Thais)
    ("do", PN_DROGA),
    ("do", BRAMA),
    ("do", DEPO_THAIS),
)
THAIS_Z_TROLLI = (
    ("start", ROZWIDLENIE),
    ("drzwi", (32657, 31965, 8), (0, -1)),
    ("lina", (32663, 31962, 8), (32663, 31961, 8), (32663, 31963, 7)),   # lina w górę z8 -> z7 (stoimy obok pola liny), lądowanie (x, y+1)
    ("drzwi", (32659, 31966, 7), (0, 1)),
    ("do", MOST_E),
) + THAIS_POWROT_KONIEC
TAM_WSPOLNA = THAIS_MOST + (
    ("do", (32613, 31976, 7)),                                           # wschodni brzeg -> południowe wejście na przełęcz z6
    ("przejscie", (32614, 31976, 7), (32614, 31975, 6)),                 # schody w górę z7 -> z6 (przełęcz nad skałą)
    ("przejscie", (32609, 31963, 6), (32608, 31963, 7)),                 # schody w dół z6 -> z7 (po stronie miasta)
)
POWROT = (
    ("start", DEPO_KAZ),
    ("przejscie", (32613, 31925, 11), (32613, 31924, 10)),               # z11 -> z10 (schody w górę)
    ("przejscie", (32605, 31920, 10), (32605, 31921, 9)),
    ("przejscie", (32613, 31921, 9), (32613, 31922, 8)),
    ("przejscie", (32603, 31925, 8), (32603, 31924, 7)),
    ("przejscie", (32602, 31923, 7), (32602, 31922, 6)),
    ("drzwi", (32611, 31921, 6), (0, -1)),
    ("przejscie", (32613, 31919, 6), (32613, 31919, 7)),                 # dziura w dół z6 -> z7 (w drugą stronę: lina)
    ("przejscie", (32609, 31963, 7), (32610, 31964, 6)),                 # schody w górę na przełęcz z6
    ("do", (32624, 31973, 6)),
    ("przejscie", (32624, 31974, 6), (32625, 31974, 7)),                 # schody w dół z6 -> z7 (wschód)
    ("do", MOST_E),
) + THAIS_POWROT_KONIEC


def drzwi_ok(m, d):
    """Drzwi = pole, które mapa uważa za ścianę, z chodliwymi polami po obu stronach w jednej osi."""
    f = m.flagi(*d)
    if not f & _mapa.SCIANA:
        return False
    x, y, z = d
    return (chodliwe(m, (x, y - 1, z)) and chodliwe(m, (x, y + 1, z))) or (chodliwe(m, (x - 1, y, z)) and chodliwe(m, (x + 1, y, z)))


def koszt_pola(m, p, cache={}):
    """Mnożnik kosztu wejścia na pole p=(x,y,z): 1 dla drogi (kolor 129), MNOZ_TEREN dla reszty, MNOZ_WODA dla koloru 40; tylko z6/z7."""
    if p[2] not in PIETRA_POWIERZCHNI:
        return 1
    k = cache.get(p)
    if k is None:
        kol = m.pole(*p)[1]
        k = 1 if kol == KOLOR_DROGI else MNOZ_WODA if kol == 40 else MNOZ_TEREN
        cache[p] = k
    return k


def astar_droga(m, start, cel, zajete, przepusc, limit=3000000):
    """A* po mapie jednego piętra z kosztem terenu (droga 1, trawa MNOZ_TEREN...). Chodliwe = widziane, nie ściana, nie flaga 2, nie w `zajete`;
    `przepusc` = klucze drzwi (x*_K+y). Ruch prosty 1, skos 3 (jak cavebot), razy mnożnik pola docelowego. Zwraca pola bez startu albo None."""
    z = start[2]
    zaj = {(p[0], p[1]) for p in zajete if p[2] == z}
    zle = _mapa.SCIANA | _mapa.BEZ_DROGI

    def wolne(x, y):
        if (x, y) in zaj:
            return False
        if (x * _mapa._K + y) in przepusc:
            return True
        f = m.flagi(x, y, z)
        return bool(f & _mapa.WIDZIANE) and not f & zle

    cx, cy = cel[0], cel[1]
    s = (start[0], start[1])
    g, skad, kopiec, gotowe = {s: 0}, {s: None}, [(abs(s[0] - cx) + abs(s[1] - cy), 0, s)], set()
    while kopiec and len(gotowe) < limit:
        _, gk, k = heapq.heappop(kopiec)
        if k in gotowe:
            continue
        gotowe.add(k)
        if k == (cx, cy):
            wynik = []
            while k != s:
                wynik.append((k[0], k[1], z))
                k = skad[k]
            return wynik[::-1]
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            n = (k[0] + dx, k[1] + dy)
            if n in gotowe or not wolne(*n):
                continue
            gn = gk + (1 if dx == 0 or dy == 0 else 3) * koszt_pola(m, (n[0], n[1], z))
            if gn < g.get(n, 1 << 60):
                g[n], skad[n] = gn, k
                heapq.heappush(kopiec, (gn + abs(n[0] - cx) + abs(n[1] - cy), gn, n))
    return None


class Planista:
    """Buduje listę punktów (x, y, z) z kroków; A* po mapie piętra, ogień/dziury/strefy = ściana."""

    def __init__(self, m, zajete):
        self.m, self.zajete = m, zajete
        self.pts, self.przejscia = [], []          # przejścia: (indeks T, T, L, rodzaj)

    def _a(self, start, cel):
        z = start[2]
        przepusc = {d[0] * _mapa._K + d[1] for d in DRZWI if d[2] == z}
        d = astar_droga(self.m, start, cel, self.zajete, przepusc)
        if d is None:
            raise SystemExit(f"brak drogi {start} -> {cel}")
        return d

    def idz(self, cel):
        if self.pts[-1] == cel:
            return
        if self.pts[-1][2] != cel[2]:
            raise SystemExit(f"idz: zmiana piętra bez przejścia {self.pts[-1]} -> {cel}")
        self.pts += self._a(self.pts[-1], cel)

    def obok(self, T):
        best = None
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            c = (T[0] + dx, T[1] + dy, T[2])
            if not chodliwe(self.m, c) or c in self.zajete:
                continue
            try:
                d = [] if c == self.pts[-1] else self._a(self.pts[-1], c)
            except SystemExit:
                continue
            if best is None or len(d) < len(best[1]):
                best = (c, d)
        if best is None:
            raise SystemExit(f"brak drogi do pola obok {T}")
        self.pts += best[1]

    def krok(self, k):
        t = k[0]
        if t == "start":
            self.pts = [k[1]]
        elif t == "do":
            self.idz(k[1])
        elif t == "drzwi":
            d, kier = k[1], k[2]
            if not drzwi_ok(self.m, d):
                raise SystemExit(f"{d}: to nie są drzwi w mapie")
            pre, po = (d[0] - kier[0], d[1] - kier[1], d[2]), (d[0] + kier[0], d[1] + kier[1], d[2])
            if not chodliwe(self.m, pre) or not chodliwe(self.m, po):
                raise SystemExit(f"drzwi {d}: pole przed {pre} albo za {po} niechodliwe")
            self.idz(pre)
            self.pts += [d, po]
        elif t == "przejscie":
            T, L = k[1], k[2]
            self.obok(T)
            self.pts += [T, L]
            self.przejscia.append((len(self.pts) - 2, T, L, "schody/dziura/rampa"))
        elif t == "lina":
            R, stoi, L = k[1], k[2], k[3]
            if abs(stoi[0] - R[0]) + abs(stoi[1] - R[1]) != 1:
                raise SystemExit(f"lina: stanie {stoi} nie jest obok {R}")
            self.idz(stoi)
            self.pts += [L]
            self.przejscia.append((len(self.pts) - 2, R, L, "lina"))
        else:
            raise SystemExit(f"nieznany krok {k}")

    def zbuduj(self, kroki):
        for k in kroki:
            self.krok(k)
        return list(self.pts)


def sprawdz(m, pts, przejscia, ogien):
    """Asercje na gotowej trasie: ciągłość, drzwi prostopadle, przejścia przez pietra.kandydaci, ogień."""
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) != 1:
            raise SystemExit(f"nieciągłość {a} -> {b}")
    for p in pts:
        if p in ogien:
            raise SystemExit(f"punkt w ogniu/buforze: {p}")
    for i in range(1, len(pts) - 1):
        a, p, b = pts[i - 1], pts[i], pts[i + 1]
        if p in DRZWI and (a[0] != b[0] and a[1] != b[1]):
            raise SystemExit(f"drzwi {p} przekraczane po skosie {a} -> {b}")
    for i, T, L, rodzaj in przejscia:
        a, b = pts[i], pts[i + 1]
        pola = [c["pole"] for c in pietra.kandydaci(m, a, b) if c["pewne"]]
        if T not in pola:
            raise SystemExit(f"przejście {rodzaj} {T} -> {L}: pietra.kandydaci nie daje go jako pewnego (daje {pola}) dla {a} -> {b}")


KOM = {
    ((32548, 32076, 7), (32549, 32076, 6)): "MOST Thais: rampa z7 w górę na pomost z6 (32549..32553); lądowanie NIEZMIERZONE w grze",
    ((32554, 32076, 6), (32555, 32076, 7)): "MOST Thais: rampa z pomostu w dół na z7; lądowanie NIEZMIERZONE w grze",
    ((32554, 32076, 7), (32553, 32076, 6)): "MOST Thais od wschodu: rampa z7 w górę na pomost z6; lądowanie NIEZMIERZONE",
    ((32548, 32076, 6), (32547, 32076, 7)): "MOST Thais od wschodu: rampa z pomostu w dół (Thais); lądowanie NIEZMIERZONE",
    ((32614, 31976, 7), (32614, 31975, 6)): "przełęcz z6 nad skałą przed Kazordoonem (jak 'most' w generuj_trasy_kazordoon_trolle.py)",
    ((32613, 31920, 7), (32613, 31922, 6)): "LINA na (32613,31920,z7): stoimy (32613,31921,z7); lądowanie (32613,31922,z6) NIESPRAWDZONE (mapa: (32613,31921,z6) to ściana)",
    ((32613, 31919, 6), (32613, 31919, 7)): "dziura w dół (w drugą stronę potrzeba liny)",
}


def meta_z(przejscia, pts, start_kom, koniec_kom):
    meta = [{"idx": 0, "typ": "start", "komentarz": start_kom}]
    for i, T, L, rodzaj in przejscia:
        dol = L[2] > T[2]
        kom = KOM.get((T, L), "")
        meta.append({"idx": i, "typ": "przed_zmiana_pietra", "komentarz": f"{rodzaj} {T[:2]} z{T[2]} -> z{L[2]}; {kom}".rstrip("; ")})
        meta.append({"idx": i + 1, "typ": "schody_w_dol" if dol else "schody_w_gore", "komentarz": f"lądowanie z{L[2]} {L[:2]}"})
    meta.append({"idx": len(pts) - 1, "typ": "koniec", "komentarz": koniec_kom})
    return sorted(meta, key=lambda e: (e["idx"], 0 if e["typ"] == "start" else 1 if e["typ"] == "przed_zmiana_pietra" else 2))


def potwory_przy_trasie(trasa, promien):
    """Spawny w promieniu `promien` od punktów trasy na tym samym piętrze -> [(odl, nazwa, x, y, z, ilosc, hp, atak, grozniejszy_niz_troll)]."""
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    troll = next(mo for mo in dane if mo["nazwa"] == "troll")
    por = {}
    for p in trasa:
        por.setdefault(p[2], []).append(p)
    out = []
    for mo in dane:
        if mo["nazwa"] == "troll":
            continue
        gr = mo["hp"] > troll["hp"] or mo["atak"] > troll["atak"]
        for s in mo.get("spawny", []):
            pts = por.get(s["z"])
            if not pts:
                continue
            od = min(max(abs(s["x"] - p[0]), abs(s["y"] - p[1])) for p in pts)
            if od <= promien:
                out.append((od, mo["nazwa"], s["x"], s["y"], s["z"], s["ilosc"], mo["hp"], mo["atak"], gr))
    return sorted(out)


def strefy_zakazane(m, ogien, dz):
    """Pola stref promienia STREFA wokół spawnów groźniejszych niż troll leżących w pasie trasy -> zbiór (x, y, z) do A* jako ściana.
    Tylko piętra z7 (droga powierzchniowa); w jaskiniach Kazordoonu trasa i tak jest wąskim korytarzem miasta."""
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    troll = next(mo for mo in dane if mo["nazwa"] == "troll")
    zle = set()
    for mo in dane:
        if mo["nazwa"] == "troll" or not (mo["hp"] > troll["hp"] or mo["atak"] > troll["atak"]):
            continue
        for s in mo.get("spawny", []):
            if s["z"] == 7 and 32330 <= s["x"] <= 32640 and 31900 <= s["y"] <= 32240:
                for dx in range(-STREFA, STREFA + 1):
                    for dy in range(-STREFA, STREFA + 1):
                        zle.add((s["x"] + dx, s["y"] + dy, 7))
    return zle


def zbuduj(z_strefami=True):
    m = _mapa.Mapa()
    dz = {tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}
    ogien = ogien_pola()
    for d in DRZWI:
        if not drzwi_ok(m, d):
            raise SystemExit(f"{d}: to nie są drzwi w mapie")
    zajete = set(dz) | ogien
    strefy = strefy_zakazane(m, ogien, dz) if z_strefami else set()
    # strefy nie mogą zamknąć punktów kontrolnych (depo, brama, mosty): ich wnętrze zwalniamy
    ok_pkt = {k[1] for k in TAM_WSPOLNA + POWROT + THAIS_DO_TROLLI + THAIS_Z_TROLLI if k[0] in ("start", "do")}
    ok_pkt |= {DZIURA_TROLLE, (32663, 31961, 8), (32663, 31963, 7)}
    zajete_tam = zajete | {p for p in strefy if p not in ok_pkt}
    wyn = {}
    for nazwa, kroki, sk, ek in (
        (f"{NAZWA}_tam", TAM_WSPOLNA + TAM_LINA, "depo Thais (z7), wygenerowane z mapy 22.10; depo i brama niezmierzone botem", "depo Kazordoon (z11), DO POTWIERDZENIA w grze"),
        (f"{NAZWA}_tam_bez_liny", TAM_WSPOLNA + TAM_BEZ_LINY, "depo Thais (z7), wariant bez liny (obejście góry od północy)", "depo Kazordoon (z11), DO POTWIERDZENIA w grze"),
        (f"{NAZWA}_powrot", POWROT, "depo Kazordoon (z11), DO POTWIERDZENIA w grze", "depo Thais (z7), pole przybycia wyprawy"),
        # trasy do jaskini trolli: ZAPISUJE je generuj_trasy_kazordoon_trolle.py (wspólny odcinek importowany stąd); tu tylko podgląd/PNG
        (f"{NAZWA}_trolle_tam", THAIS_DO_TROLLI, "depo Thais (z7)", "rozwidlenie z8 (32647,32003)"),
        (f"{NAZWA}_trolle_powrot", THAIS_Z_TROLLI, "rozwidlenie z8 (32647,32003)", "depo Thais (z7), pole przybycia wyprawy"),
    ):
        pl = Planista(m, zajete_tam)
        pts = pl.zbuduj(kroki)
        sprawdz(m, pts, pl.przejscia, ogien)
        wyn[nazwa] = dict(pts=pts, przejscia=list(pl.przejscia), meta=meta_z(pl.przejscia, pts, sk, ek))
    return m, wyn, ogien, strefy


def podsumuj(m, wyn):
    for n, w in wyn.items():
        pts = w["pts"]
        kroki = sum(1 for a, b in zip(pts, pts[1:]) if a[2] == b[2])
        skosy = sum(1 for a, b in zip(pts, pts[1:]) if a[2] == b[2] and a[0] != b[0] and a[1] != b[1])
        print(f"{n}: {len(pts)} pkt, kroków po piętrze {kroki} (w tym skosów {skosy}), przejść {len(w['przejscia'])}, "
              f"piętra {sorted({p[2] for p in pts})}, start {pts[0]}, koniec {pts[-1]}")
        pw = [p for p in pts if p[2] in PIETRA_POWIERZCHNI]
        dr = sum(1 for p in pw if m.pole(*p)[1] == KOLOR_DROGI)
        print(f"   po drodze (kolor {KOLOR_DROGI}) {dr}/{len(pw)} pól powierzchni z6/z7 = {100 * dr / max(1, len(pw)):.0f}%")
        print(f"   czas marszu (krok 0,6-0,9 s + ~3 s/przejście): {(kroki + skosy) * 0.6 + 3 * len(w['przejscia']):.0f}-"
              f"{(kroki + skosy) * 0.9 + 3 * len(w['przejscia']):.0f} s (skos liczony podwójnie)")
        for i, T, L, r in w["przejscia"]:
            print(f"   idx {i}: {r} {T} -> {L}")
        gro = [t for t in potwory_przy_trasie(pts, PROMIEN_RAPORTU) if t[8]]
        print(f"   spawny groźniejsze niż troll (hp>50 lub atak>10) <= {PROMIEN_RAPORTU} pól od trasy (odl, nazwa, x, y, z, ilość, hp, atak):")
        for t in gro[:14]:
            print("     ", t[:8])
        if not gro:
            print("      brak")
        tr = [t for t in potwory_przy_trasie(pts, 0) if not t[8]]
        print(f"   inne spawny (słabsze) na samej trasie (odl 0): {len(tr)}: {[(t[1], t[2], t[3], t[4]) for t in tr[:8]]}")


def obrazy(m, wyn):
    from PIL import Image, ImageDraw
    kol = {7: (230, 40, 40), 6: (255, 140, 0), 8: (40, 120, 255), 9: (150, 60, 220), 10: (30, 170, 90), 11: (0, 200, 200)}

    def panel(z, box, sc, pts, tytul, wiecej=()):
        x0, y0, x1, y1 = box
        im = Image.new("RGB", ((x1 - x0 + 1) * sc, (y1 - y0 + 1) * sc))
        d = ImageDraw.Draw(im)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                p = m.pole(x, y, z)
                if not p or not p[0] & 1:
                    c = (0, 0, 0)
                else:
                    c = _mapa._kolor_tibii(p[1])
                    if p[0] & 4:
                        c = tuple(v * 2 // 5 for v in c)
                    if p[0] & 2:
                        c = (255, 220, 0)
                d.rectangle([(x - x0) * sc, (y - y0) * sc, (x - x0 + 1) * sc - 1, (y - y0 + 1) * sc - 1], fill=c)
        for (nzw, lst, kolor) in wiecej:
            for p in lst:
                if p[2] == z and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                    d.rectangle([(p[0] - x0) * sc, (p[1] - y0) * sc, (p[0] - x0 + 1) * sc - 1, (p[1] - y0 + 1) * sc - 1], fill=kolor)
        for p in pts:
            if p[2] == z and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                d.rectangle([(p[0] - x0) * sc, (p[1] - y0) * sc, (p[0] - x0 + 1) * sc - 1, (p[1] - y0 + 1) * sc - 1], fill=kol[z])
        d.text((3, 3), tytul, fill=(255, 255, 255))
        return im

    tam, bez, pow_ = wyn[f"{NAZWA}_tam"]["pts"], wyn[f"{NAZWA}_tam_bez_liny"]["pts"], wyn[f"{NAZWA}_powrot"]["pts"]
    jedn = tam + pow_
    out = ROOT / "dane_tibia" / "mapy"
    ob = panel(7, (32330, 31895, 32640, 32240), 3, jedn, "z7: trasa tam+powrot (czerwone z7, pomaranczowe z6)")
    d = ImageDraw.Draw(ob)
    d.rectangle([(32547 - 32330) * 3 - 6, (32076 - 31895) * 3 - 6, (32555 - 32330) * 3 + 6, (32077 - 31895) * 3 + 6], outline=(255, 255, 255))
    d.text(((32547 - 32330) * 3 - 10, (32076 - 31895) * 3 - 20), "MOST Thais", fill=(255, 255, 255))
    d.text(((32348 - 32330) * 3, (32225 - 31895) * 3 + 6), "depo Thais", fill=(255, 255, 255))
    ob.save(out / f"{NAZWA}.png")
    most = Image.new("RGB", (2 * 17 * 14 + 10, 11 * 14))
    most.paste(panel(7, (32543, 32072, 32559, 32082), 14, jedn, "z7"), (0, 0))
    most.paste(panel(6, (32543, 32072, 32559, 32082), 14, jedn, "z6 (pomost)"), (17 * 14 + 10, 0))
    most.save(out / f"{NAZWA}_most.png")
    box = (32540, 31895, 32640, 31985)
    sc = 6
    w, h = (box[2] - box[0] + 1) * sc, (box[3] - box[1] + 1) * sc
    kaz = Image.new("RGB", (2 * w + 10, 2 * h + 10))
    kaz.paste(panel(7, box, sc, tam + bez, "z7: tam(lina)+bez liny", [("bez", [p for p in bez if p not in tam], (255, 0, 255))]), (0, 0))
    kaz.paste(panel(6, box, sc, jedn + bez, "z6"), (w + 10, 0))
    kaz.paste(panel(8, box, sc, jedn + bez, "z8"), (0, h + 10))
    kaz.paste(panel(9, box, sc, jedn + bez, "z9 (+z10, z11 poza ramką)"), (w + 10, h + 10))
    kaz.save(out / f"{NAZWA}_kaz.png")
    # trasa do jaskini trolli: tam (czerwone z7, pomaranczowe z6, niebieskie z8) + powrot (jasnozielone, rysowane pod spodem)
    tt, tp = wyn[f"{NAZWA}_trolle_tam"]["pts"], wyn[f"{NAZWA}_trolle_powrot"]["pts"]
    box = (32330, 31930, 32680, 32240)
    sc = 3
    tr = panel(7, box, sc, tt, "z7: Thais -> trolle pod Kazordoonem (czerwone = tam; jasnozielone = tylko powrot; zolte kropki = przejscia)",
               [("powrot", [p for p in tp if p not in tt], (120, 255, 120))])
    d = ImageDraw.Draw(tr)
    d.text(((32348 - box[0]) * sc, (32225 - box[1]) * sc + 6), "depo Thais", fill=(255, 255, 255))
    d.text(((32547 - box[0]) * sc - 10, (32076 - box[1]) * sc - 20), "MOST", fill=(255, 255, 255))
    d.text(((32663 - box[0]) * sc - 40, (31962 - box[1]) * sc - 14), "dziura z7 (troll)", fill=(255, 255, 255))
    tr.save(out / f"{NAZWA}_trolle.png")
    return [f"{NAZWA}.png", f"{NAZWA}_most.png", f"{NAZWA}_kaz.png", f"{NAZWA}_trolle.png"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("--bez-stref", action="store_true", help="nie traktuj stref wokół groźniejszych spawnów jako ściany")
    a = ap.parse_args(argv)
    m, wyn, ogien, strefy = zbuduj(not a.bez_stref)
    print(f"ogień+bufor: {len(ogien)} pól, strefy zakazane z7: {len(strefy)} pól")
    podsumuj(m, wyn)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    for n, w in wyn.items():
        if n.startswith(f"{NAZWA}_trolle_"):
            continue                    # te dwa podglądy zapisuje generuj_trasy_kazordoon_trolle.py (jedno źródło, bez kopii)
        print("zapisano", trasa_io.zapisz(n, w["pts"], w["meta"]))
    pliki = obrazy(m, wyn)
    dane = {n: {"pkt": len(w["pts"]), "przejscia": [(i, T, L, r) for i, T, L, r in w["przejscia"]]} for n, w in wyn.items()}
    (ROOT / "dane_tibia" / "mapy" / f"{NAZWA}.json").write_text(json.dumps(dane, ensure_ascii=False, indent=1))
    print("zapisano obrazy", pliki, "i dane_tibia/mapy/thais_kazordoon.json (wpisu w mapy.json NIE dodano)")


if __name__ == "__main__":
    main()
