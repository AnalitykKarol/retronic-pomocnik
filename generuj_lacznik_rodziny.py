#!/usr/bin/env python3
"""Łączniki między piętrami jednej jaskini (26.10, Karol: zmiana spotu w obrębie jaskini nie może wymagać wyjścia na z7).
Dla rodzin z dziurami i linami (edron_trolle, edron_gobliny) buduje, dla KAŻDEJ pary (pętla źródłowa A -> mapa docelowa B), której dojście nie działa
z całej pętli A (`rodziny_dojscie.macierz`), krótki łącznik: dojście z miejsca pętli A (stanie przy linie, lina w górę, ew. podajniki) do miejsca, od którego
dojście mapy B działa, i dokleja resztę dojścia B. Łącznik to trasa `trasy/<rodzina>_lacznik_<A>_<B>` (+ .meta); mapa-wariant `<B>__z__<A>` w mapy.json
(pętla i potwory z B, dojście = łącznik, dojscie_z_dowolnego_pietra) i wpis w spoty_nadzorca.json (`baza` = B, `auto: false` w pliku; efektywne auto/powód dziedziczy od B w spoty.wczytaj).
Bez zapisu liczy i weryfikuje (`rodziny_dojscie.weryfikuj_lacznik`: z każdego trzeciego punktu pętli A dojście = łącznik zadziała jak w mozg).

  python3 -I generuj_lacznik_rodziny.py            liczy i wypisuje (nic nie zapisuje)
  python3 -I generuj_lacznik_rodziny.py --zapisz   zapisuje trasy, mapy.json i spoty_nadzorca.json (ponowny odczyt tuż przed zapisem, tylko moje klucze, atomowo)
Cofnięcie: usunąć trasy/*_lacznik_*, wpisy z kluczem zawierającym `__z__` w mapy.json i spoty_nadzorca.json (albo przywrócić *.bak-20261026-z-dowolnego).
Każde przejście liną/dziurą w łączniku jest NIEZWERYFIKOWANE na żywo (z mapy klienta i znanych pól lin)."""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("RETRONIC_TESTY", "1")
import mapa as _mapa  # noqa: E402
import rodziny_dojscie as R  # noqa: E402
import trasa_io  # noqa: E402

RODZINY = ["edron_trolle", "edron_gobliny"]
MAPY = ROOT / "mapy.json"
TABELA = ROOT / "dane_tibia" / "spoty_nadzorca.json"
SEP = "__z__"
FILTR = [a for a in sys.argv[1:] if not a.startswith("--")]


def nazwy(fam, A, B):
    return f"{fam}_lacznik_{A}_{B}", f"{B}{SEP}{A}"


def zapis_atomowy(plik, dane):
    tmp = Path(str(plik) + ".tmp-lacznik")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, plik)


def zbierz(m=None):
    """[(fam, A, B, punkty, meta, opis)] zweryfikowanych łączników + [(fam, A, B, powód)] nieudanych."""
    m = m or _mapa.mapa()
    t = R.swiat()
    ok, zle = [], []
    for fam in RODZINY:
        if FILTR and fam not in FILTR:
            continue
        for A, B, w in R.macierz(t, fam, m):
            if w["brak"] == 0 or B not in R.CELE.get(fam, [B]):
                continue
            r = R.zbuduj_lacznik(t, fam, A, B, m)
            if r is None:
                zle.append((fam, A, B, "planer nie znalazł drogi"))
                continue
            pts, meta, op = r
            dobry, uw = R.weryfikuj_lacznik(t, fam, A, B, pts, m)
            if not dobry:
                zle.append((fam, A, B, "; ".join(uw[:2])))
                continue
            ok.append((fam, A, B, pts, meta, op))
    return t, ok, zle


def wpisy(t, fam, A, B, pts, op):
    """(klucz mapy, wpis mapy.json, wpis tabeli) wariantu."""
    plik, klucz = nazwy(fam, A, B)
    base_m = json.loads(MAPY.read_text(encoding="utf-8"))[B]
    base_t = json.loads(TABELA.read_text(encoding="utf-8"))["spoty"][B]
    liny = "; ".join(op) if op else "bez zmiany piętra liną (przejście schodami/podajniki po tym samym piętrze)"
    wm = {k: v for k, v in base_m.items() if k not in ("opis", "dojscie", "dojscie_z_dowolnego_pietra")}
    wm = {"opis": (f"WARIANT NADZORCY (nie wybieraj ręcznie; to {B} z dojściem z innego piętra): dojście {plik} ({len(pts)} pkt) z pętli {A} (26.10, "
                   f"rodziny_dojscie.py: łącznik od miejsca na pętli {A} do miejsca, od którego działa dojście {B}). Przejścia: {liny}. NIEZWERYFIKOWANE na żywo "
                   f"(z mapy klienta i znanych pól lin); pętla i potwory jak {B}"),
          **wm, "dojscie": plik, "dojscie_z_dowolnego_pietra": True}
    wt = {k: v for k, v in base_t.items() if k not in ("powod", "auto", "waga")}
    wt.update({"waga": base_t.get("waga", 1.0), "auto": False, "baza": B,
               "powod": (f"wariant-łącznik spotu {B} (dojście z pętli {A}); EFEKTYWNE auto i powód dziedziczy po {B} w spoty.wczytaj (nowy kod); `auto: false` w pliku to "
                         f"zabezpieczenie dla STAREGO kodu spoty.py w żywym procesie (bez obsługi `baza` wybrałby wariant z z7 i dojście byłoby śmieciem)")})
    if op:
        wt["wymaga_dodatkowo"] = ["lina"]
    return klucz, wm, wt


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    m = _mapa.mapa()
    t, ok, zle = zbierz(m)
    for fam, A, B, pts, meta, op in ok:
        print(f"OK   {fam:14} {A:28} -> {B:30} {len(pts):4} pkt  {'; '.join(op) or '-'}")
    for fam, A, B, pw in zle:
        print(f"NIE  {fam:14} {A:28} -> {B:30} {pw}")
    if "--zapisz" not in argv:
        print("(bez --zapisz: nic nie zapisano)")
        return 0
    for fam, A, B, pts, meta, op in ok:
        plik, _ = nazwy(fam, A, B)
        trasa_io.zapisz(plik, pts, meta)
    mapy = json.loads(MAPY.read_text(encoding="utf-8"))
    tab = json.loads(TABELA.read_text(encoding="utf-8"))
    zm = zt = False
    for fam, A, B, pts, meta, op in ok:
        k, wm, wt = wpisy(t, fam, A, B, pts, op)
        if mapy.get(k) != wm:
            mapy[k], zm = wm, True
        if tab["spoty"].get(k) != wt:
            tab["spoty"][k], zt = wt, True
    if zm:
        zapis_atomowy(MAPY, mapy)
    if zt:
        zapis_atomowy(TABELA, tab)
    print(f"zapisano: {len(ok)} łączników; mapy.json {'zmieniony' if zm else 'bez zmian'}, spoty_nadzorca.json {'zmieniony' if zt else 'bez zmian'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
