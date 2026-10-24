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
            elif f & _mapa.BEZ_DROGI:
                zle_t.append(f"flaga 2 {q}")
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
    if a.zapisz:
        print("zapisano", trasa_io.zapisz(NAZWA, pts, meta))
    else:
        print("(bez --zapisz: nic nie zapisano)")


if __name__ == "__main__":
    main()
