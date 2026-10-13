#!/usr/bin/env python3
"""Przechwyt celu w pościgu: punkt, w którym cel BĘDZIE, gdy do niego dotrzemy (zamiast biegu do jego
bieżącej pozycji). Czysta funkcja: bez I/O, bez zegara, bez importu cavebota i mapy (dostaje wywołania).

  wybierz(poz, historia, teraz, przechodnie, predkosc, ...) -> dict

Model (zgodny z telemetrią 11.10):
  - nasz krok na pole o prędkości v trwa ceil(10000*v/230/50)*50 ms (v12 -> 0,55 s, v16 -> 0,70 s, v20 -> 0,90 s),
    pomnożone przez `mnoznik` (sprawność pętli, np. 1,0 = idealnie);
  - ruch następuje OD RAZU, a koszt kroku płaci się PO nim (serwer Tibii: pozycja zmienia się na starcie
    kroku, kolejny krok dopiero po odczekaniu); skos kosztuje `skos_koszt` kroków prostych, ale tylko
    po nim; skosy w ogóle tylko gdy `skosy` (domyślnie skos_koszt < 2.0, jak POSCIG_SKOS w cavebot.py);
  - cel porusza się ze stałą prędkością wektorową wyliczoną z historii (ostatnie 3-5 zmian pozycji
    z czasami), po drodze zatrzymuje go ściana; cel zawracający/oscylujący albo stojący nie jest
    przewidywany (fallback: cel = bieżąca pozycja, kierunek None = niech decyduje dotychczasowy kod).

Szukamy (Dijkstra po czasie dojścia) najwcześniejszego pola, na które wejdziemy w chwili, gdy przewidziany
cel stoi w odległości Chebysheva <= `zasieg` (1 = walka wręcz). Horyzont: `horyzont` kroków celu od
ostatnio widzianej pozycji (4-5), dalej nie przewidujemy.
"""

import heapq
import math

HORYZONT = 4              # kroków celu naprzód od ostatniej widzianej pozycji
ZASIEG = 1                # pola (Chebyshev): tyle od celu = przechwycony
PREDKOSC_GRACZA = 230     # "speed" postaci (level 6); krok = ceil(10000*v/speed/50)*50 ms
V_DOMYSLNA = 12           # prędkość pola, gdy mapa jej nie zna
V_CELU_MAX = 2.0          # pola/s: wyżej to artefakt próbkowania
V_CELU_MIN = 0.25         # pola/s: wolniej = cel stoi
PROMIEN = 14              # pola od nas: dalej nie szukamy
HIST_MAX = 5              # ile ostatnich zmian pozycji celu bierzemy
KOSTKI = ((1, 0), (-1, 0), (0, 1), (0, -1))
SKOSY = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def czas_kroku(v, predkosc_gracza=PREDKOSC_GRACZA):
    """Czas (s) jednego kroku prostego po polu o prędkości v (jak serwer: zaokrąglenie w górę do 50 ms)."""
    v = v if v and v > 0 else V_DOMYSLNA
    return math.ceil(10000.0 * v / predkosc_gracza / 50.0) * 50.0 / 1000.0


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _linia(a, b):
    """Pola od a (bez) do b (z) po prostej Bresenhama."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    n = max(dx, dy)
    out = []
    for i in range(1, n + 1):
        out.append((x0 + int(round((x1 - x0) * i / n)), y0 + int(round((y1 - y0) * i / n))))
    return out


def _dedup(historia):
    """Historia (x, y, t) bez powtórzeń tej samej pozycji z rzędu (zostaje czas PIERWSZEGO zobaczenia)."""
    out = []
    for h in sorted(historia, key=lambda e: e[2]):
        if out and (out[-1][0], out[-1][1]) == (h[0], h[1]):
            continue
        out.append((h[0], h[1], h[2]))
    return out[-HIST_MAX:]


def model_celu(historia, teraz, przechodnie):
    """Przewidywanie ruchu celu. -> (stan, ostatnia (x, y), pozycja_w(T), v_pol_s)
    stan: "idzie" | "stoi" | "brak_historii" | "zawraca".
    pozycja_w(T): pozycja celu T sekund od `teraz` (T >= 0), z klamrą na ścianie."""
    h = _dedup(historia)
    if not h:
        return "brak_historii", None, None, 0.0
    xl, yl, tl = h[-1]
    ost = (xl, yl)
    stoi = lambda T: ost
    if len(h) < 2:
        return "brak_historii", ost, stoi, 0.0
    # zawracanie/oscylacja: powrót na pozycję już odwiedzoną w oknie albo skok przeciwny do dotychczasowego
    poz_hist = [(e[0], e[1]) for e in h]
    if len(set(poz_hist)) < len(poz_hist):
        return "zawraca", ost, stoi, 0.0
    if len(h) >= 3:
        d_prev = (h[-2][0] - h[0][0], h[-2][1] - h[0][1])
        d_last = (h[-1][0] - h[-2][0], h[-1][1] - h[-2][1])
        if d_prev[0] * d_last[0] + d_prev[1] * d_last[1] < 0:
            return "zawraca", ost, stoi, 0.0
        # skręt w poprzek (np. prawo, potem w górę) jest dozwolony: schodki po skosie to zwykły ruch celu
    dt = tl - h[0][2]
    if dt <= 0:
        return "brak_historii", ost, stoi, 0.0
    vx, vy = (xl - h[0][0]) / dt, (yl - h[0][1]) / dt
    w = math.hypot(vx, vy)
    if w > V_CELU_MAX:
        k = V_CELU_MAX / w
        vx, vy, w = vx * k, vy * k, V_CELU_MAX
    if w < V_CELU_MIN:
        return "stoi", ost, stoi, 0.0
    # cel, który nie zmienił pozycji od dłużej niż ~2 jego kroki, już prawdopodobnie stoi
    krok_celu = 1.0 / max(abs(vx), abs(vy))
    if teraz - tl > 2.0 * krok_celu:
        return "stoi", ost, stoi, 0.0

    def pozycja_w(T):
        tau = teraz + T - tl
        if tau <= 0:
            return ost
        surowa = (xl + int(vx * tau), yl + int(vy * tau))      # obcięcie ku zeru: krok pojawia się po pełnym czasie
        p = ost
        for pole in _linia(ost, surowa):
            if przechodnie(pole[0], pole[1]) is not True:
                break
            p = pole
        return p

    return "idzie", ost, pozycja_w, max(abs(vx), abs(vy))


def wybierz(poz, historia, teraz, przechodnie, predkosc=None, wolny_za=0.0, zajete=(), skos_koszt=3.0,
            skosy=None, horyzont=HORYZONT, zasieg=ZASIEG, mnoznik=1.0, predkosc_gracza=PREDKOSC_GRACZA,
            promien=PROMIEN):
    """Wybór kroku przechwytującego.

    poz          (x, y) pole, z którego zaczyna się następny krok (koniec kroku w toku = Q w _poscig_decyzja)
    historia     [(x, y, t), ...] ostatnie zmiany pozycji celu (t = chwila PIERWSZEGO zobaczenia pozycji, s)
    teraz        bieżący czas (ten sam zegar co t w historii)
    przechodnie  f(x, y) -> True/False/None  (None = nieznane: traktowane jak ściana)
    predkosc     f(x, y) -> prędkość pola (np. mapa.pole(x,y,z)[2]) albo None (V_DOMYSLNA)
    wolny_za     s do chwili, gdy wolno nam ruszyć z `poz` (0 = stoimy; reszta kroku w toku)
    zajete       pola z innymi stworami/graczami (nie wchodzimy)
    skos_koszt   POSCIG_SKOS_KOSZT; skosy=None -> dozwolone tylko gdy skos_koszt < 2.0 (jak cavebot._poscig_skos)
    horyzont     ile kroków celu naprzód od ostatnio widzianej pozycji
    mnoznik      mnożnik naszego czasu kroku (np. 1/0,77 przy realnej sprawności pętli)

    -> dict: kierunek (dx, dy) albo None; cel (x, y): pozycja celu w chwili przechwytu (przy fallbacku:
       bieżąca pozycja celu); pole (x, y) albo None: pole, na którym go złapiemy; t: s do przechwytu;
       kroki: ile naszych kroków; stan: stan modelu celu; powod: "przechwyt" | "obok" | "cel_stoi" |
       "brak_historii" | "zawraca" | "poza_horyzontem" | "brak_drogi";
       cel_prowadzenia (x, y) przy "poza_horyzontem": gdzie cel będzie na końcu horyzontu."""
    poz = (poz[0], poz[1])
    stan, ost, pozycja_w, w = model_celu(historia, teraz, przechodnie)
    wyn = {"kierunek": None, "cel": ost, "pole": None, "t": None, "kroki": 0, "stan": stan, "powod": stan,
           "cel_prowadzenia": None}
    if ost is None:
        wyn["powod"] = "brak_historii"
        return wyn
    if _cheb(poz, ost) <= zasieg:
        wyn["powod"] = "obok"
        return wyn
    if stan in ("zawraca", "brak_historii"):
        return wyn
    if skosy is None:
        skosy = skos_koszt < 2.0
    zaj = {(p[0], p[1]) for p in zajete}
    # horyzont czasu: cel przeszedł `horyzont` pól od ostatnio widzianej pozycji
    tl = max((e[2] for e in historia), default=teraz)
    if stan == "stoi":
        T_h = 8.0                                     # cel stoi: zwykłe dojście, krótki horyzont wystarczy
    else:
        T_h = max(0.0, tl - teraz) + horyzont / max(w, 1e-6)

    def v_pola(x, y):
        v = predkosc(x, y) if predkosc is not None else None
        return v if v and v > 0 else V_DOMYSLNA

    # Dijkstra po czasie ODJAZDU: odj(pole) = chwila, gdy wolno wykonać kolejny krok z pola
    start_odj = max(0.0, wolny_za)
    odj = {poz: start_odj}
    rodzic = {poz: None}
    kopiec = [(start_odj, 0, poz)]
    ile = 0
    ruchy = list(KOSTKI) + (list(SKOSY) if skosy else [])
    najlepszy = None
    while kopiec:
        t_odj, _, p = heapq.heappop(kopiec)
        if t_odj > odj.get(p, 1e18) + 1e-9:
            continue
        if t_odj > T_h:
            break
        for dx, dy in ruchy:
            n = (p[0] + dx, p[1] + dy)
            if n in rodzic and rodzic[n] is not None and odj[n] <= t_odj + 1e-9:
                continue
            if n in zaj or max(abs(n[0] - poz[0]), abs(n[1] - poz[1])) > promien:
                continue
            if przechodnie(n[0], n[1]) is not True:
                continue
            przyb = t_odj                               # wejście na pole następuje od razu
            kr = czas_kroku(v_pola(n[0], n[1]), predkosc_gracza) * mnoznik
            if dx and dy:
                kr *= skos_koszt
            if n in odj and odj[n] <= przyb + kr:
                continue
            odj[n] = przyb + kr
            rodzic[n] = p
            ile += 1
            # przyb liczone osobno: kandydat na złapanie
            c = pozycja_w(przyb)
            heapq.heappush(kopiec, (przyb + kr, ile, n))
            if _cheb(n, c) <= zasieg:
                klucz = (przyb, abs(n[0] - c[0]) + abs(n[1] - c[1]))
                if najlepszy is None or klucz < najlepszy[0]:
                    najlepszy = (klucz, n, c, przyb)
        if najlepszy is not None and t_odj >= najlepszy[3]:
            break                                       # kolejne pola przybywałyby później
    if najlepszy is None:
        wyn["powod"] = "poza_horyzontem" if stan == "idzie" else "brak_drogi"
        if stan == "idzie":
            wyn["cel_prowadzenia"] = pozycja_w(T_h)
        return wyn
    _, pole, c, przyb = najlepszy
    p, kroki = pole, 1
    while rodzic[p] is not None and rodzic[p] != poz:
        p = rodzic[p]
        kroki += 1
    wyn.update(kierunek=(p[0] - poz[0], p[1] - poz[1]), cel=c, pole=pole, t=przyb, kroki=kroki,
               powod="cel_stoi" if stan == "stoi" else "przechwyt")
    return wyn
