#!/usr/bin/env python3
"""Ab'Dendriel, trolle z10/z9 (abdendriel_trolle_z10_z9): trasa POWROTU do depo Ab'Dendriel (24.10, Marinarra). Nic nie wysyła do gry:

  python3 -I generuj_powrot_abdendriel.py [--zapisz]        bez --zapisz tylko liczy, sprawdza i drukuje podsumowanie

Powód: wyprawa.PLANY_PK nie znał Ab'Dendriel (tylko Edron, Kazordoon, Port Hope, Rook, Thais), więc panel miał `plan_depo_dostepny: false`,
a ręczne „Wróć do miasta” (wroc.sh -> plik WROC -> Wyprawa._okazja_wroc) kończyło się "brak planu". Powstaje trasy/abdendriel_trolle_do_depo
(+ .meta) = cztery kawałki:
  1. z10: pole stania OBOK pola liny (32668,31624,z10) (pole liny pod dziurą z9, tą samą, którą dojście abdendriel_z9_do_z10 schodzi w dół);
     stoimy na (32668,31623,z10) (północ), NIE na (32668,31625,z10) (to dziura z10 -> z11) ani na polach prostopadle obok niej;
  2. LINA z10 -> z9: lądowanie (32668,31625,z9) = (x, y+1) pola liny; z9 A* po mapie (omija ogień, kandydatów trucizny, nauczone dziury) do
     (32658,31644,z9) w jaskini;
  3. z9 korytarz wieży schodowej = NAGRANIE „depo -> trolle” (trasy/abdendriel_depo_trolle_nagranie.json, ręcznie przeszedł Karol 24.10 11:05)
     ODWRÓCONE: dwoje drzwi na prostych odcinkach (32658,31645,z9) i (32655,31655,z9) (mapa widzi je jako ścianę; nagranie przeszło przez nie,
     obsługa DRZWI_TRASA w cavebocie), między nimi A* po mapie w obrębie sali; koniec = pole przed schodami (32654,31671,z9);
  4. SCHODY z9 -> z8: pole schodów (32654,31670,z9) na północ od pola stania, lądowanie (32654,31669,z8) (wzorzec pietra.py "pewne"; w wypad.zbuduj_etapy
     rozpoznane przez _schody_przed_ladowaniem); z8 korytarz x=32655 na południe i odwrócone nagranie z8 do pola startu nagrania.
KONIEC TRASY = POCZĄTEK NAGRANIA „depo_trolle” = (32679,31687,z8). To jest ZASTĘPCZA DECYZJA (be-dev, do przeglądu): pozycji depo Ab'Dendriel nie
ma w żadnych danych, jest tylko nazwa nagrania i to, że zaczyna się ono na z8 w sali (32679..32682,31683..31689). Stała DEPO_STOI to jedyne miejsce,
które trzeba zmienić po jednym pomiarze na żywo (stań przy skrzyni depo, odczytaj pozycję, wpisz, uruchom z --zapisz).
Pominięte celowo: dwa kółka nagrania przez z7 (wejście schodami (32654,31674,z8) i zejście z powrotem (32654,31673,z7) -> (32654,31675,z8)); korytarz z8
x=32655 łączy te same pola bez zmiany piętra.
NIEZWERYFIKOWANE NA ŻYWO: lina z10 -> z9 na (32668,31624,z10); schody W GÓRĘ (32654,31670,z9) (nagranie szło w dół, mapa i pietra.kandydaci "pewne");
oba drzwi (jeśli zamknięte na klucz, trasa stoi); lina w plecaku Marinarry; położenie depo (patrz wyżej).
Wpis do wyprawa.PLANY_PK: patrz plan_pk(). Test: testy/test_powrot_abdendriel.py.

DOJŚCIE Z DEPO NA PĘTLĘ z10 (24.10 19:12, Marinarra stoi w depo (32679,31687,z8), mapa abdendriel_trolle_z10_z9): trasy/abdendriel_depo_do_z10 (+ .meta) =
ta sama droga co powrót, odwrócona (JEDNO źródło geometrii, bez dublowania tras): z8 nagranie Karola od depo do pola obok schodów w dół (32655,31670,z8),
SCHODY W DÓŁ (32654,31670,z8) (krok; lądowanie (32654,31671,z9)), korytarz z9, dwoje drzwi na klucz 2970, jaskinia z9 (A* z powrotu odwrócony) do pola liny
(32668,31625,z9), potem DZIURA (32668,31624,z9) -> z10 (32668,31624,z10) = koniec dojścia = start pętli z10 (jak dawne abdendriel_z9_do_z10). Dla postaci
na dowolnym punkcie tej drogi mozg.dojscie_od_pozycji bierze najbliższy punkt (mapa ma dojscie_z_dowolnego_pietra). Dawne abdendriel_z9_do_z10 (17 pkt od
(32675,31633,z9)) jest ZASTĄPIONE: jego początek leży 13 pól od tej drogi. Wyjście serwisu = WYJSCIE_SERWISU = pierwsze pole jaskini za obojgiem drzwi, leży
NA tej trasie (generuj_serwis_abdendriel czyta stałą stąd). Test: testy/test_dojscie_depo_abdendriel.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_abdendriel_trolle as AB  # noqa: E402  (ROPE_B, NIE_STAWAJ, kandydaci_trucizny, z_buforem, dziury_nauczone)
import generuj_trasy_edron_wschod as _ogn  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402
import wypad  # noqa: E402

NAZWA = "abdendriel_trolle_do_depo"
NAGRANIE = "abdendriel_depo_trolle_nagranie"
STOI10 = (32668, 31623, 10)            # pole stania obok pola liny (32668,31624,z10): północ, z10 rząd y=31623 ma x=32667..32669 chodliwe
LINA10 = AB.ROPE_B                     # (32668,31624,10): pole liny, NIE wchodzimy (pod dziurą z9 (32668,31624,z9))
LAD9 = (32668, 31625, 9)               # lądowanie liny = (x, y+1) pola liny = start pętli z9
JASKINIA9 = (32658, 31644, 9)          # koniec A* po jaskini z9 = ostatnie pole przed drzwiami (32658,31645,z9) od północy
DRZWI9 = [(32658, 31645, 9), (32655, 31655, 9)]   # ściany w mapie na prostych odcinkach nagrania (przeszły przez nie)
KLUCZ_DRZWI = 2970                     # 24.10 (Karol: Marinarra „nie umie uzyc klucza na drzwiach”): a copper key z plecaka Marinarry (Elathriel, 5000 gp); NIEPOTWIERDZONE, ze pasuje do obu drzwi
KLUCZE_DRZWI = tuple((d, KLUCZ_DRZWI) for d in DRZWI9)   # -> meta ("klucz") i wyprawa.PLANY_PK["klucze"]; wypad._drzwi: krok, Use klucza na drzwiach, krok
PO_DRZWIACH_A = (32658, 31646, 9)      # pierwsze pole sali za drzwiami (32658,31645)
SALA_DO = (32655, 31654, 9)            # ostatnie pole sali przed drzwiami (32655,31655)
PO_DRZWIACH_B = (32655, 31656, 9)      # pierwsze pole korytarza za drzwiami (32655,31655)
STOI_SCHODY9 = (32654, 31671, 9)       # pole stania przed schodami W GÓRĘ (32654,31670,z9)
SCHODY9 = (32654, 31670, 9)            # flaga 2, kolor 210: schody z9 -> z8, NIE wchodzimy na nie poza przejściem
LAD8 = (32654, 31669, 8)               # lądowanie z8 = (x, y-1) schodów
SCHODY8_W_DOL = (32654, 31670, 8)      # schody z8 -> z9 tuż obok lądowania: NIE wchodzić (wracałoby na z9)
SCHODY8_W_GORE = (32654, 31674, 8)     # schody z8 -> z7 (nagranie: pętla przez z7), omijane
Z8_KORYTARZ = [(32655, 31670, 8), (32655, 31673, 8)]   # x=32655: pole obok schodów w dół i obok schodów w górę, bez wchodzenia na nie
NAZWA_DOJSCIA = "abdendriel_depo_do_z10"
DZIURA9 = (32668, 31624, 9)            # dziura z9 -> z10 (pole nad polem liny (32668,31624,z10)); dojście wchodzi na nią krokiem
LAD10 = (32668, 31624, 10)             # lądowanie po dziurze = koniec dojścia = start pętli abdendriel_trolle_z10_petla
SCHODY8_DOL = (32654, 31670, 8)        # schody z8 -> z9 (flaga 2 na obu piętrach, kolor 210), lądowanie (32654,31671,z9); nagranie Karola przeszło tędy
STOI_SCHODY8 = (32655, 31670, 8)       # pole stania obok schodów w dół (z nagrania)
WYJSCIE_SERWISU = JASKINIA9            # (32658,31644,9): pierwsze pole jaskini ZA obojgiem drzwi (patrząc z depo); leży na trasie dojścia
DEPO_STOI = (32679, 31687, 8)          # SUBSTITUTE DECISION (be-dev, do przeglądu leada): pierwszy punkt nagrania „depo -> trolle”; depo NIEPOMIERZONE


def plan_pk():
    """Wpis do wyprawa.PLANY_PK. "drzwi": True = Wyprawa._zbuduj_depo wydziela etapy DRZWI (Use + krok) dla dwojga drzwi z9. Bez "wyjscia": plik "do" zawiera całą drogę z przejściami pięter (wzór trolle_kazordoon_z9, thais_pn_z9).
    "z" = nagranie depo -> trolle (kończy się w jaskini z9 (32658,31640), nie na z10; używane tylko przy WYPRAWA_DEPO_POWROT=1, u Marinarry 0)."""
    return {"nazwa": "abdendriel_trolle_z10", "do": NAZWA + ".json", "z": NAGRANIE + ".json", "npc": None, "prefix": False, "drzwi": True, "klucze": KLUCZE_DRZWI}


def _zle(m):
    """Ogień + kandydaci trucizny, każdy z buforem 1 (jak w generatorze spotu): ściany dla A*."""
    kand = AB.kandydaci_trucizny(m)
    return AB.z_buforem({(x, y, z) for x, y, z, _ in kand}) | _ogn.ogien_pola()


def _astar(m, a, b, zle, dz):
    """Pola A* po mapie od `a` do `b` (z `b`, bez `a`), na jednym piętrze, bez stref zakazanych i nauczonych dziur."""
    z = a[2]
    sc = [p for p in zle if p[2] == z] + [p for p in dz if p[2] == z]
    d = m.droga(a, b, zajete=sc, dlugosc=0, limit=400000)
    if d is None:
        raise SystemExit(f"brak drogi po mapie {a} -> {b}")
    return [(q[0], q[1], z) for q in d]


def zbuduj():
    m = _mapa.Mapa()
    zle = _zle(m)
    dz = AB.dziury_nauczone()
    nagr, _ = trasa_io.wczytaj(NAGRANIE)
    if tuple(nagr[0]) != DEPO_STOI:
        raise SystemExit(f"nagranie zaczyna się w {nagr[0]}, a DEPO_STOI to {DEPO_STOI}")
    # odwrócone nagranie z8: od (32655,31677,z8) do początku (pierwsze 23 punkty, przed pierwszym wejściem na z7)
    i7 = next(i for i, q in enumerate(nagr) if q[2] == 7)
    nagr8 = nagr[:i7 - 1]                                   # kończy się (32655,31677,z8); punkt (32655,31674) pomijamy (obok schodów w górę)
    if nagr8[-1] != (32655, 31677, 8) or any(q[2] != 8 for q in nagr8):
        raise SystemExit("odcinek z8 nagrania niespójny")
    pts, meta = [STOI10], [{"idx": 0, "typ": "start", "komentarz": f"pole stania obok pola liny {LINA10[:2]} z10 (północ); pole liny wolne, "
                                                                   f"NIE stawać na {sorted(AB.NIE_STAWAJ)[0][:2]} (dziura z10 -> z11)"}]
    meta.append({"idx": 0, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA na polu {LINA10[:2]} z10 (pod dziurą z9 (32668,31624), tą z dojścia abdendriel_z9_do_z10): lądowanie (x, y+1) = {LAD9[:2]} z9. "
                              "NIEZWERYFIKOWANE na żywo; potrzebna lina w plecaku"})
    # --- z9: lądowanie, jaskinia (A*), drzwi, sala (A*), drzwi, korytarz (A*) do pola przed schodami ---
    pts.append(LAD9)
    meta.append({"idx": 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z9 {LAD9[:2]} (start pętli z9), tuż obok dziury (32668,31624,z9): nie wchodzić"})
    pts += _astar(m, LAD9, JASKINIA9, zle, dz)
    pts.append(PO_DRZWIACH_A)                               # prosty odcinek (32658,31644) -> (32658,31646) przez drzwi (32658,31645)
    meta.append({"idx": len(pts) - 2, "typ": "drzwi", "komentarz": f"drzwi {DRZWI9[0][:2]} z9: ściana w mapie, nagranie przeszło przez nie; DRZWI_TRASA; na klucz {KLUCZ_DRZWI}", "klucz": KLUCZ_DRZWI})
    pts += _astar(m, PO_DRZWIACH_A, SALA_DO, zle, dz)
    pts.append(PO_DRZWIACH_B)                               # prosty odcinek (32655,31654) -> (32655,31656) przez drzwi (32655,31655)
    meta.append({"idx": len(pts) - 2, "typ": "drzwi", "komentarz": f"drzwi {DRZWI9[1][:2]} z9: ściana w mapie, nagranie przeszło przez nie; DRZWI_TRASA; na klucz {KLUCZ_DRZWI}", "klucz": KLUCZ_DRZWI})
    pts += _astar(m, PO_DRZWIACH_B, STOI_SCHODY9, zle, dz)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"SCHODY W GÓRĘ {SCHODY9[:2]} z9 (flaga 2, kolor 210) na północ od pola stania {STOI_SCHODY9[:2]}; lądowanie (x, y-1) = {LAD8[:2]} z8. "
                              "NIEZWERYFIKOWANE w tę stronę (nagranie zeszło schodami z (32655,31670,z8))"})
    # --- z8: lądowanie, korytarz x=32655, nagranie odwrócone do początku ---
    pts += [LAD8] + Z8_KORYTARZ
    meta.append({"idx": len(pts) - 3, "typ": "schody_w_gore", "komentarz": f"lądowanie z8 {LAD8[:2]}; obok niego schody w dół {SCHODY8_W_DOL[:2]} (nie wchodzić), idź korytarzem x=32655"})
    pts += list(reversed(nagr8))
    meta.append({"idx": len(pts) - 1, "typ": "koniec",
                 "komentarz": f"{DEPO_STOI[:2]} z8 = początek nagrania „depo -> trolle”; położenie depo NIEPOMIERZONE (zastępcza decyzja, patrz generuj_powrot_abdendriel.py)"})
    kontrole(pts)
    return pts, meta


def _linia(a, b):
    n = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    return [(a[0] + round((b[0] - a[0]) * i / n), a[1] + round((b[1] - a[1]) * i / n), a[2]) for i in range(1, n)] if n > 1 else []


def _kontrola_pol(pts, m, flaga2_ok=()):
    """Wspólna kontrola pól trasy (powrót i dojście): skoki > 4 pól, ściany/niewidziane (poza drzwiami z DRZWI9 na prostym odcinku), flaga 2.
    `flaga2_ok` = pola przejść pięter, na które trasa wchodzi celowo (dziura). Zwraca (lista błędów, zbiór drzwi znalezionych na trasie)."""
    zle_t = []
    drzwi_ok = set()
    for a, b in zip(pts, pts[1:]):
        if a[2] != b[2]:
            continue
        if max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 4:
            zle_t.append(f"skok {a}->{b}")
        for q in [a] + _linia(a, b):
            f = m.flagi(*q)
            if q in DRZWI9:
                drzwi_ok.add(q)                              # ściana na prostym odcinku = drzwi z nagrania
                if not (a[0] == b[0] or a[1] == b[1]):
                    zle_t.append(f"drzwi {q} na odcinku po skosie")
            elif not f & _mapa.WIDZIANE or f & _mapa.SCIANA:
                zle_t.append(f"ściana/niewidziane {q}")
            elif f & _mapa.BEZ_DROGI and q not in flaga2_ok:
                zle_t.append(f"flaga 2 {q}")
    return zle_t, drzwi_ok


def kontrole(pts):
    m = _mapa.Mapa()
    zle = _zle(m)
    dz = AB.dziury_nauczone()
    przejscia = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    oczek = [(STOI10, LAD9), (STOI_SCHODY9, LAD8)]
    if przejscia != oczek:
        raise SystemExit(f"przejścia pięter inne niż oczekiwane: {przejscia}")
    # zbuduj_etapy ma je odtworzyć: lina (cel = pole liny) i schody (cel = pole schodów, krok), a drzwi muszą być rozpoznane
    et = wypad.zbuduj_etapy(pts, m, wypad.drzwi_z_mapy(pts, m))
    przej = [e for e in et if e["typ"] in ("LINA", "DZIURA")]
    if [e["typ"] for e in przej] != ["LINA", "LINA"] or przej[0]["cel"] != LINA10 or przej[0].get("schody") \
            or przej[1]["cel"] != SCHODY9 or not przej[1].get("schody"):
        raise SystemExit(f"etapy przejść niezgodne z planem: {przej}")
    zle_t, drzwi_ok = _kontrola_pol(pts, m)
    if zle_t:
        raise SystemExit("trasa niepoprawna: " + "; ".join(zle_t[:6]))
    if drzwi_ok != set(DRZWI9):
        raise SystemExit(f"drzwi na trasie {sorted(drzwi_ok)} != oczekiwane {DRZWI9}")
    # pola liny, schodów, dziur i schodów w dół/górę z8 nie są na trasie
    zakaz = {LINA10, SCHODY9, SCHODY8_W_DOL, SCHODY8_W_GORE, (32668, 31625, 10), (32668, 31624, 9)}
    if zakaz & set(pts):
        raise SystemExit(f"trasa wchodzi na pole przejścia: {sorted(zakaz & set(pts))}")
    zle_p = sorted(q for q in pts if q in zle)
    if zle_p:
        raise SystemExit(f"punkty na ogniu/trucliźnie (bufor 1): {zle_p[:6]}")
    wd = sorted(q for q in pts if q in dz)
    if wd:
        raise SystemExit(f"trasa zawiera nauczoną dziurę: {wd}")
    # mapa potwierdza układ: lina (kolor 210 pole liny + flaga 2 dziury nad nim), schody w górę (flaga 2 na z9 i z8, oba kolor 210)
    fl, fd = m.flagi(*LINA10), m.flagi(LINA10[0], LINA10[1], 9)
    if not (m.pole(*LINA10)[1] == 210 and fl & 1 and not fl & (2 | 4) and fd & 2 and not fd & 4):
        raise SystemExit(f"układ liny {LINA10} nie potwierdzony mapą")
    fs = m.flagi(*SCHODY9)
    if not (m.pole(*SCHODY9)[1] == 210 and fs & 2 and not fs & 4):
        raise SystemExit(f"schody {SCHODY9} nie potwierdzone mapą")
    # drzwi rozpoznane jak w cavebocie (trasa_io.drzwi_na_trasie): oba, wejście od północy
    dr = [d["pole"] for d in trasa_io.drzwi_na_trasie(pts, m)]
    if sorted(dr) != sorted(DRZWI9):
        raise SystemExit(f"drzwi_na_trasie: {dr} != {DRZWI9}")
    print(f"kontrole powrotu: {len(pts)} pkt, przejścia {przejscia}; etapy {[(e['typ'], e['cel']) for e in przej]}; drzwi {dr}; "
          "zero ścian/ognia/trucizny/dziur nauczonych, pola liny i schodów poza trasą")


def zbuduj_dojscie(pts_powrot=None):
    """Dojście z depo na pętlę z10 = trasa powrotu ODWRÓCONA (jedna geometria): bez STOI10 (z10) i bez LAD8 (lądowanie schodów w górę, w dół
    nie występuje), z dopisaną dziurą z9 -> z10 na końcu. Zwraca (punkty, meta)."""
    if pts_powrot is None:
        pts_powrot, _ = zbuduj()
    rev = [q for q in reversed(pts_powrot[1:]) if q != LAD8]
    if rev[0] != DEPO_STOI or rev[-1] != LAD9:
        raise SystemExit(f"odwrócony powrót zaczyna się w {rev[0]} i kończy w {rev[-1]}, oczekiwane {DEPO_STOI} i {LAD9}")
    pts = rev + [DZIURA9, LAD10]
    i_sch = pts.index(STOI_SCHODY8)
    if pts[i_sch + 1] != STOI_SCHODY9:
        raise SystemExit(f"po polu przy schodach w dół {STOI_SCHODY8} oczekiwane lądowanie {STOI_SCHODY9}, jest {pts[i_sch + 1]}")
    kontrole_dojscia(pts)         # geometria i kontrole na liście BEZ pól drzwi (drzwi to w mapie ściana: _kontrola_pol je rozpoznaje po przeskoku o 2 pola)
    # 24.10 (pomiar w atrapie, 5 startów): same pola PRZED i ZA drzwiami (przeskok o 2 pola przez ścianę) dawały zderzenia z murem (KROK_ZLY x2, 4-9 zbędnych kroków,
    # 77 s zamiast 59 s od depo): lookahead celował za drzwi bez A*. Pole drzwi jako PUNKT TRASY (DRZWI_TRASA: nagranie przeszło przez te pola) prowadzi drzwi-hak
    # (cavebot._drzwi_klucz_tick/_drzwi_hak, klucz z _drzwi_lista), zero zderzeń. Wstawiamy je dopiero po kontrolach, w pary punktów po obu stronach drzwi.
    for d in (DRZWI9[1], DRZWI9[0]):
        j = next((k for k in range(len(pts) - 1) if pts[k][2] == d[2] and abs(pts[k][0] - d[0]) + abs(pts[k][1] - d[1]) == 1
                  and abs(pts[k + 1][0] - d[0]) + abs(pts[k + 1][1] - d[1]) == 1 and pts[k][:2] != pts[k + 1][:2]
                  and (pts[k][0] == pts[k + 1][0] == d[0] or pts[k][1] == pts[k + 1][1] == d[1])), None)
        if j is None:
            raise SystemExit(f"nie znalazłem pary punktów po obu stronach drzwi {d}")
        pts.insert(j + 1, d)
    i_a, i_b = pts.index(DRZWI9[0]), pts.index(DRZWI9[1])      # indeksy pól drzwi (meta: gdzie leży drzwi na trasie)
    i_wyj = pts.index(WYJSCIE_SERWISU)
    meta = [
        {"idx": 0, "typ": "start", "komentarz": f"depo Ab'Dendriel {DEPO_STOI[:2]} z8 (ZASTĘPCZE, NIEPOMIERZONE), początek nagrania „depo -> trolle”; z dowolnego punktu tej drogi dojście bierze najbliższy punkt"},
        {"idx": i_sch, "typ": "przed_zmiana_pietra", "komentarz": f"SCHODY W DÓŁ {SCHODY8_DOL[:2]} z8 (flaga 2 na z8 i z9, kolor 210) obok pola stania {STOI_SCHODY8[:2]}; lądowanie (x, y+1) = (32654, 31671) z9. "
                                                                  "Nagranie Karola 24.10 11:05 przeszło tędy w tę stronę"},
        {"idx": i_sch + 1, "typ": "schody_w_dol", "komentarz": "lądowanie z9 (32654,31671) tuż pod schodami w górę (32654,31670,z9): NIE iść na północ po x=32654, idź na x=32655"},
        {"idx": i_b, "typ": "drzwi", "komentarz": f"drzwi {DRZWI9[1][:2]} z9 od południa: ściana w mapie, nagranie przeszło przez nie; DRZWI_TRASA; na klucz {KLUCZ_DRZWI}", "klucz": KLUCZ_DRZWI},
        {"idx": i_a, "typ": "drzwi", "komentarz": f"drzwi {DRZWI9[0][:2]} z9 od południa: ściana w mapie, nagranie przeszło przez nie; DRZWI_TRASA; na klucz {KLUCZ_DRZWI}", "klucz": KLUCZ_DRZWI},
        {"idx": i_wyj, "typ": "wyjscie_serwisu", "komentarz": f"{WYJSCIE_SERWISU[:2]} z9: pierwsze pole jaskini ZA obojgiem drzwi = pole, na którym serwis kończy krok wyjscie (generuj_serwis_abdendriel)"},
        {"idx": len(pts) - 2, "typ": "przed_zmiana_pietra", "komentarz": f"DZIURA {DZIURA9[:2]} z9 -> z10 (flaga 2; pod nią pole liny {LAD10[:2]} z10); pole liny z9 {LAD9[:2]} tuż obok. Jak w dawnym abdendriel_z9_do_z10"},
        {"idx": len(pts) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z10 {LAD10[:2]} = start pętli abdendriel_trolle_z10_petla; NIE stawać na (32668,31625,10) (dziura z10 -> z11)"},
        {"idx": len(pts) - 1, "typ": "koniec", "komentarz": "start pętli abdendriel_trolle_z10_petla. NIEPRZEJŚTE NA ŻYWO w całości; drzwi na klucz 2970 i schody w dół z8->z9 nagrane/odtworzone, dziura z9->z10 niezmierzona"},
    ]
    return pts, meta


def kontrole_dojscia(pts):
    import pietra  # noqa: PLC0415
    m = _mapa.Mapa()
    zle = _zle(m)
    dz = AB.dziury_nauczone()
    przejscia = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    oczek = [(STOI_SCHODY8, STOI_SCHODY9), (DZIURA9, LAD10)]
    if przejscia != oczek:
        raise SystemExit(f"przejścia pięter dojścia inne niż oczekiwane: {przejscia}")
    # cavebot (pietra.kandydaci) ma wybrać dokładnie te pola przejść, jako pewne
    for (a, b), pole in zip(przejscia, (SCHODY8_DOL, DZIURA9)):
        k = pietra.kandydaci(m, a, b)
        if not k or not k[0]["pewne"] or tuple(k[0]["pole"]) != pole:
            raise SystemExit(f"pietra.kandydaci({a} -> {b}) = {k[:1]}, oczekiwane pewne {pole}")
    zle_t, drzwi_ok = _kontrola_pol(pts, m, flaga2_ok=(DZIURA9,))
    if zle_t:
        raise SystemExit("dojście niepoprawne: " + "; ".join(zle_t[:6]))
    if drzwi_ok != set(DRZWI9):
        raise SystemExit(f"drzwi na dojściu {sorted(drzwi_ok)} != oczekiwane {DRZWI9}")
    dr = [d["pole"] for d in trasa_io.drzwi_na_trasie(pts, m)]
    if sorted(dr) != sorted(DRZWI9) or dr != [DRZWI9[1], DRZWI9[0]]:
        raise SystemExit(f"drzwi_na_trasie dojścia: {dr}, oczekiwane kolejno {[DRZWI9[1], DRZWI9[0]]}")
    zakaz = {SCHODY9, SCHODY8_DOL, SCHODY8_W_GORE, LAD8, (32668, 31625, 10)}      # LINA10 = LAD10 to koniec dojścia (jak w dawnym abdendriel_z9_do_z10)
    if zakaz & set(pts):
        raise SystemExit(f"dojście wchodzi na pole przejścia: {sorted(zakaz & set(pts))}")
    zle_p = sorted(q for q in pts if q in zle)
    if zle_p:
        raise SystemExit(f"punkty dojścia na ogniu/trucliźnie (bufor 1): {zle_p[:6]}")
    wd = sorted(q for q in pts if q in dz)
    if wd:
        raise SystemExit(f"dojście zawiera nauczoną dziurę: {wd}")
    if WYJSCIE_SERWISU not in pts or pts.index(WYJSCIE_SERWISU) <= max(pts.index(PO_DRZWIACH_A), pts.index(PO_DRZWIACH_B)):
        raise SystemExit("wyjście serwisu nie leży na dojściu za obojgiem drzwi")
    fs = m.flagi(*SCHODY8_DOL)
    fd = m.flagi(*DZIURA9)
    if not (m.pole(*SCHODY8_DOL)[1] == 210 and fs & 2 and not fs & 4 and m.flagi(SCHODY8_DOL[0], SCHODY8_DOL[1], 9) & 2):
        raise SystemExit(f"schody w dół {SCHODY8_DOL} nie potwierdzone mapą")
    if not (fd & 2 and not fd & 4 and m.flagi(*LINA10) & 1):
        raise SystemExit(f"dziura {DZIURA9} -> pole liny {LINA10} nie potwierdzone mapą")
    print(f"kontrole dojścia: {len(pts)} pkt, przejścia {przejscia}; drzwi {dr} (klucz {KLUCZ_DRZWI}); wyjście serwisu {WYJSCIE_SERWISU} na trasie; "
          "zero ścian/ognia/trucizny/dziur nauczonych, pola liny i schodów poza trasą")


# --- POWRÓT Z z12 I z11 (25.10, Marinarra/Marianni): lina w górę z12 -> z11 -> z10, dalej trasa powrotu z z10 (jedna geometria, bez dublowania) ---
NAZWA_Z12 = "abdendriel_trolle_z12_do_depo"
PLAN_Z12 = "abdendriel_trolle_z12"
ROPE12 = (32668, 31624, 12)            # pole liny z12 = lądowanie po dziurze z11 (32668,31624,z11); NIEPOTWIERDZONE na żywo (spadek z11 -> z12 nigdy nie nagrany)
H11 = (32668, 31624, 11)             # dziura z11 -> z12 (flaga 2, kolor 210); NIE wchodzić
STOI12 = (32668, 31623, 12)            # pole stania obok pola liny z12 (północ; z12 x=32668..32669 chodliwe), lądowanie liny (x, y+1) = (32668,31625,z11)
PRZED12 = [(32668, 31620, 12), (32668, 31621, 12), (32668, 31622, 12)]   # wąski korytarz x=32668 na północ od pola stania: punkty "do" na z12 (wybór planu, wejście na trasę)
LAD11 = (32668, 31625, 11)             # lądowanie liny z12 = pole liny z11 (pod dziurą z10 (32668,31625,z10), którą bot nauczył się jako wpadnięcie)
STOI11 = (32667, 31625, 11)            # pole stania obok pola liny z11: PROSTOPADLE (zachód), NIE (32668,31626,z11) (taki sam x,y jak lądowanie = tryb "własne")
LAD10U = (32668, 31626, 10)             # lądowanie liny z11 = (x, y+1) pola liny; pod dziurą z10 (32668,31625) = południe od niej, trzeba ją obejść
H10 = AB.H10                           # (32668,31625,10): dziura z10 -> z11 (nauczona w dziury_nauczone.json), NIE wchodzić


def zbuduj_z12(pts_powrot=None):
    """Trasa powrotu z z12 (i z11) = [korytarz z12, LINA z12 -> z11, krok, LINA z11 -> z10, obejście dziury z10 A*] + trasa powrotu z z10
    (abdendriel_trolle_do_depo bez zmian, od STOI10). Zwraca (punkty, meta)."""
    if pts_powrot is None:
        pts_powrot, meta_p = zbuduj()
    else:
        meta_p = None
    m = _mapa.Mapa()
    zle = _zle(m)
    dz = AB.dziury_nauczone()
    kolej = _astar(m, LAD10U, STOI10, zle | {LINA10}, dz)     # z10: obejście dziury (32668,31625) i pola liny (32668,31624) po zachodniej stronie
    if pts_powrot[0] != STOI10:
        raise SystemExit(f"powrót zaczyna się w {pts_powrot[0]}, oczekiwane {STOI10}")
    pre = PRZED12 + [STOI12, LAD11, STOI11, LAD10U] + [q for q in kolej if q != LAD10U]
    if pre[-1] != STOI10:
        raise SystemExit(f"obejście z10 kończy się w {pre[-1]}, oczekiwane {STOI10}")
    pts = pre[:-1] + list(pts_powrot)
    n = len(pre) - 1
    meta = [{"idx": 0, "typ": "start", "komentarz": f"korytarz z12 x=32668 na północ od pola stania {STOI12[:2]} (pole liny z12 {ROPE12[:2]} = lądowanie po dziurze z11); "
                                                    "z dalszych pól z12 dojście robi A* po piętrze (wyprawa.droga_do_depo)"}]
    i12 = pts.index(STOI12)
    meta.append({"idx": i12, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA z12 -> z11 na polu {ROPE12[:2]} (pod dziurą z11 {H11[:2]}): lądowanie (x, y+1) = {LAD11[:2]} z11. NIEPOTWIERDZONE na żywo: "
                              "dziura z11 -> z12 nie była nigdy przeszła (wzorzec dziura + pole liny jak z9/z10), lina w plecaku"})
    meta.append({"idx": i12 + 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z11 {LAD11[:2]} = pole liny z11 (tuż pod dziurą z11 {H11[:2]}: NIE iść na północ); krok na zachód {STOI11[:2]}"})
    meta.append({"idx": i12 + 2, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA z11 -> z10 na polu {LAD11[:2]} (pod dziurą z10 {H10[:2]}, nauczoną jako wpadnięcie): stoimy PROSTOPADLE obok na {STOI11[:2]}, lądowanie (x, y+1) = {LAD10U[:2]} z10. "
                              "Lina z10 -> z9 na tym samym wzorcu działała na żywo 24.10 15:48; sama lina z11 niepotwierdzona"})
    meta.append({"idx": i12 + 3, "typ": "schody_w_gore", "komentarz": f"lądowanie z10 {LAD10U[:2]} POŁUDNIE od dziury z10 {H10[:2]} (nie wchodzić); dalej A* na zachód od dziury i pola liny {LINA10[:2]} do {STOI10[:2]}"})
    if meta_p is None:
        _, meta_p = zbuduj()
    for md in meta_p:
        if md.get("typ") == "start":
            continue
        md = dict(md)
        md["idx"] = md["idx"] + n
        meta.append(md)
    kontrole_z12(pts)
    return pts, meta


def kontrole_z12(pts):
    import pietra  # noqa: PLC0415
    m = _mapa.Mapa()
    zle = _zle(m)
    dz = AB.dziury_nauczone()
    przejscia = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    oczek = [(STOI12, LAD11), (STOI11, LAD10U), (STOI10, LAD9), (STOI_SCHODY9, LAD8)]
    if przejscia != oczek:
        raise SystemExit(f"przejścia pięter powrotu z z12 inne niż oczekiwane: {przejscia}")
    for (a, b), pole in zip(przejscia[:2], (ROPE12, LAD11)):         # pietra.kandydaci ma wskazać dokładnie te pola liny jako pewne
        k = pietra.kandydaci(m, a, b)
        if not k or not k[0]["pewne"] or tuple(k[0]["pole"]) != pole or tuple(k[0]["lad"]) != b:
            raise SystemExit(f"pietra.kandydaci({a} -> {b}) = {k[:1]}, oczekiwane pewne {pole}")
    et = wypad.zbuduj_etapy(pts, m, wypad.drzwi_z_mapy(pts, m))
    przej = [e for e in et if e["typ"] == "LINA"]
    if [e["cel"] for e in przej[:2]] != [ROPE12, LAD11] or any(e.get("schody") or e.get("wlasne") for e in przej[:2]):
        raise SystemExit(f"etapy liny z12/z11 niezgodne z planem: {przej[:2]}")
    zle_t, drzwi_ok = _kontrola_pol(pts, m)
    if zle_t:
        raise SystemExit("trasa z z12 niepoprawna: " + "; ".join(zle_t[:6]))
    if drzwi_ok != set(DRZWI9):
        raise SystemExit(f"drzwi na trasie z z12 {sorted(drzwi_ok)} != oczekiwane {DRZWI9}")
    zakaz = {ROPE12, H11, H10, LINA10, (32668, 31624, 9), SCHODY9, SCHODY8_W_DOL, SCHODY8_W_GORE}
    if zakaz & set(pts):
        raise SystemExit(f"trasa z z12 wchodzi na pole przejścia: {sorted(zakaz & set(pts))}")
    zle_p = sorted(q for q in pts if q in zle)
    if zle_p:
        raise SystemExit(f"punkty na ogniu/trucliźnie (bufor 1): {zle_p[:6]}")
    wd = sorted(q for q in pts if q in dz)
    if wd:
        raise SystemExit(f"trasa z z12 zawiera nauczoną dziurę: {wd}")
    # mapa potwierdza układ obu lin: kolor 210 na polu liny, flaga 2 (dziura) nad nim, brak flagi 4
    for R, G_ in ((ROPE12, H11), (LAD11, H10)):
        fl, fd = m.flagi(*R), m.flagi(G_[0], G_[1], G_[2])
        if not (m.pole(*R)[1] == 210 and fl & 1 and not fl & (2 | 4) and fd & 2 and not fd & 4):
            raise SystemExit(f"układ liny {R} nie potwierdzony mapą")
    print(f"kontrole powrotu z z12: {len(pts)} pkt, przejścia {[(a[2], b[2]) for a, b in przejscia]}; zero ścian/ognia/trucizny/dziur, pola liny i dziur poza trasą")


def plan_pk_z12():
    """Wpis do wyprawa.PLANY_PK dla powrotu z z12/z11: "do" = NAZWA_Z12, reszta jak plan_pk() (te same drzwi i klucze)."""
    p = dict(plan_pk())
    p["nazwa"], p["do"] = PLAN_Z12, NAZWA_Z12 + ".json"
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    pts, meta = zbuduj()
    z = {}
    for q in pts:
        z[q[2]] = z.get(q[2], 0) + 1
    print(f"{NAZWA}: {len(pts)} pkt ({', '.join(f'z{k}: {v}' for k, v in sorted(z.items()))}), długość {trasa_io.dlugosc(pts)} pól, "
          f"start {pts[0]}, koniec {pts[-1]}, meta {len(meta)}")
    dpts, dmeta = zbuduj_dojscie(pts)
    dz = {}
    for q in dpts:
        dz[q[2]] = dz.get(q[2], 0) + 1
    print(f"{NAZWA_DOJSCIA}: {len(dpts)} pkt ({', '.join(f'z{k}: {v}' for k, v in sorted(dz.items()))}), długość {trasa_io.dlugosc(dpts)} pól, "
          f"start {dpts[0]}, koniec {dpts[-1]}, meta {len(dmeta)}")
    zpts, zmeta = zbuduj_z12(pts)
    zz = {}
    for q in zpts:
        zz[q[2]] = zz.get(q[2], 0) + 1
    print(f"{NAZWA_Z12}: {len(zpts)} pkt ({', '.join(f'z{k}: {v}' for k, v in sorted(zz.items()))}), długość {trasa_io.dlugosc(zpts)} pól, "
          f"start {zpts[0]}, koniec {zpts[-1]}, meta {len(zmeta)}")
    if a.zapisz:
        print("zapisano", trasa_io.zapisz(NAZWA_Z12, zpts, zmeta))
        print("zapisano", trasa_io.zapisz(NAZWA, pts, meta))
        print("zapisano", trasa_io.zapisz(NAZWA_DOJSCIA, dpts, dmeta))
    else:
        print("(bez --zapisz: nic nie zapisano)")


if __name__ == "__main__":
    main()
