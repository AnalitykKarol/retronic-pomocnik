#!/usr/bin/env python3
"""Tabela spotów i wybór spotu dla postaci (SPEC_wybor_spotu_1021, Q5). Czyste funkcje + CLI tylko do odczytu.

  python3 -I spoty.py tabela             wszystkie spoty z kolumnami wyliczonymi (miasto, piętra, dojście, wymagany ekwipunek, widełki)
  python3 -I spoty.py sprawdz            rozbieżności spoty_nadzorca.json z mapy.json i trasami (kod 1, gdy są)
  RETRONIC_ID=<id> python3 -I spoty.py ekwipunek    odczyt liny i łopaty z pamięci gry tej instancji (JSON; tylko odczyt)

`wybierz(postac, zajete, historia)` nic nie zapisuje i niczego nie uruchamia: dostaje fakty o postaci, zwraca decyzję z uzasadnieniem."""
import json
import os
import random
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
if str(KATALOG) not in sys.path:
    sys.path.insert(0, str(KATALOG))       # python3 -I nie dodaje katalogu skryptu: import liny/loot/pietra/wypad
PLIK = KATALOG / "dane_tibia" / "spoty_nadzorca.json"
ID_LOPATA = 3457                  # jak wypad.ID_LOPATA (stała zduplikowana, żeby nie ładować wypad.py tylko dla liczby)
LEKKIE_Z = 7                      # dojście z depo działa tylko ze z7 (uruchom.sh), chyba że mapa ma dojscie_z_dowolnego_pietra


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# ---------- geometria: miasto z pozycji ----------
def miasto_z_pozycji(poz, miasta):
    """Nazwa miasta, w którego prostokącie (x, y; piętro bez znaczenia, jaskinie wliczone) leży pozycja, albo None."""
    if not poz or len(poz) < 2:
        return None
    x, y = poz[0], poz[1]
    for nazwa, r in sorted(miasta.items()):
        if r["x"][0] <= x <= r["x"][1] and r["y"][0] <= y <= r["y"][1]:
            return nazwa
    return None


# ---------- trasy i wymagania ekwipunku ----------
def rozwiaz_trase(korzen, trasa):
    """`patrol` / `patrol:X` -> trasa awaryjna z miejsca_X.json (jak mozg.rozwiaz_patrol); zwykła nazwa bez zmian."""
    if trasa != "patrol" and not str(trasa).startswith("patrol:"):
        return trasa
    baza = trasa.split(":", 1)[1] if ":" in trasa else "kanaly2"
    plik = Path(korzen) / "trasy" / f"miejsca_{baza}.json"
    if plik.is_file():
        try:
            baza = json.loads(plik.read_text(encoding="utf-8")).get("trasa") or baza
        except (OSError, ValueError):
            pass
    return baza


def punkty_trasy(korzen, nazwa):
    """[(x, y, z)] z trasy/<nazwa>.json albo None (brak pliku / zły format)."""
    try:
        d = json.loads((Path(korzen) / "trasy" / f"{nazwa}.json").read_text(encoding="utf-8"))
        return [tuple(int(v) for v in p[:3]) for p in d]
    except (OSError, ValueError, TypeError):
        return None


def zasypane_domyslne():
    """Pola zasypanych dziur (z, na którym się stoi): pietra.ZASYPANE + zapamiętane przejścia `lopata` (wypad.przejscia_nauczone)."""
    wynik = set()
    try:
        import pietra  # noqa: PLC0415
        wynik |= {tuple(p) for p in pietra.ZASYPANE}
    except Exception:       # noqa: BLE001
        pass
    try:
        import wypad  # noqa: PLC0415
        for k, v in wypad.przejscia_nauczone().items():
            if isinstance(v, dict) and v.get("tryb") == "lopata":
                pole, z_do = k.split(">")
                x, y, z = (int(c) for c in pole.split(","))
                if int(z_do) == z + 1:
                    wynik.add((x, y, z))
    except Exception:       # noqa: BLE001
        pass
    return wynik


def wymaga_lopaty(punkty, zasypane):
    """Przejścia w dół a -> b (z+1), przy których leży zasypana dziura (<= 1 pole od a i od b, jak lina). -> lista (a, b, dziura)."""
    wyn = []
    for a, b in zip(punkty, punkty[1:]):
        if b[2] != a[2] + 1:
            continue
        for s in sorted(zasypane):
            if s[2] == a[2] and _cheb(s, a) <= 1 and _cheb(s, b) <= 1:
                wyn.append((a, b, s))
                break
    return wyn


class Spot:
    def __init__(self, mapa):
        self.mapa = mapa
        self.miasto = self.jaskinia = self.potwory = self.dojscie = self.trasa = None
        self.poziom = (1, 99)
        self.poziom_zrodlo = "domyslne"
        self.waga = 1.0
        self.auto = True
        self.powod = ""
        self.pietra = []
        self.z_dowolnego_pietra = False
        self.wymaga = set()                 # {"lina", "lopata", ...}
        self.wymaga_opis = {}               # "lina" -> "dojście gobliny_edron_z_depo (1 przejście)"
        self.miasto_z_geometrii = None
        self.brak_tras = []
        self.start_z = None                 # piętro pierwszego punktu dojścia albo None

    def dane(self):
        return {k: (sorted(v) if isinstance(v, set) else v) for k, v in self.__dict__.items()}


class Tabela:
    def __init__(self):
        self.miasta = {}
        self.spoty = {}
        self.nieopisane = []                # mapy z mapy.json bez wpisu w spoty_nadzorca.json (wykluczone)
        self.osierocone = []                # wpisy w spoty_nadzorca.json bez mapy w mapy.json
        self.blad = None
        self.zakladane = set()              # przedmioty, które ma każda postać (Karol): bez sprawdzania odczytu

    def jaskinia_mapy(self, mapa):
        s = self.spoty.get(mapa)
        return s.jaskinia if s else mapa


def wczytaj(korzen=None, plik=None, liny_znane=None, zasypane=None):
    """Tabela spotów: spoty_nadzorca.json + mapy.json + trasy (wymagania wyliczane na bieżąco). Błąd pliku -> Tabela z `blad` i bez spotów."""
    korzen = Path(korzen or KATALOG)
    plik = Path(plik) if plik else korzen / "dane_tibia" / "spoty_nadzorca.json"
    t = Tabela()
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
        t.miasta = {k: v for k, v in dane["miasta"].items() if not k.startswith("_")}
        t.zakladane = {str(x) for x in dane.get("zakladany_ekwipunek", []) if isinstance(x, str)}
        wpisy = {k: v for k, v in dane["spoty"].items() if not k.startswith("_")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        t.blad = f"brak albo uszkodzony {plik.name}: {e!r}"
        return t
    try:
        mapy = {k: v for k, v in json.loads((korzen / "mapy.json").read_text(encoding="utf-8")).items()
                if not k.startswith("_") and isinstance(v, dict)}
    except (OSError, ValueError) as e:
        t.blad = f"brak albo uszkodzony mapy.json: {e!r}"
        return t
    if liny_znane is None:
        try:
            import liny  # noqa: PLC0415
            liny_znane = liny.znane_liny()
        except Exception:       # noqa: BLE001
            liny_znane = set()
    if zasypane is None:
        zasypane = zasypane_domyslne()
    try:
        import liny as liny_mod  # noqa: PLC0415
        wymaga_liny = liny_mod.wymaga_liny
    except Exception:       # noqa: BLE001
        wymaga_liny = lambda pts, znane: []     # noqa: E731
    for mapa, m in mapy.items():
        w = wpisy.get(mapa)
        if w is None:
            t.nieopisane.append(mapa)
            continue
        s = Spot(mapa)
        s.miasto = w.get("miasto")
        s.jaskinia = w.get("jaskinia") or mapa
        s.poziom = tuple(int(v) for v in (w.get("poziom") or (1, 99)))
        s.poziom_zrodlo = w.get("poziom_zrodlo", "domyslne")
        s.waga = float(w.get("waga", 1.0))
        s.auto = bool(w.get("auto", True))
        s.powod = w.get("powod", "")
        s.potwory = m.get("potwory")
        s.dojscie = m.get("dojscie")
        s.z_dowolnego_pietra = bool(m.get("dojscie_z_dowolnego_pietra"))
        s.trasa = rozwiaz_trase(korzen, m.get("trasa"))
        pts_doj = punkty_trasy(korzen, s.dojscie) if s.dojscie else None
        pts_trasa = punkty_trasy(korzen, s.trasa)
        for nazwa, pts in ((s.dojscie, pts_doj), (s.trasa, pts_trasa)):
            if nazwa and pts is None:
                s.brak_tras.append(nazwa)
        wszystkie = (pts_doj or []) + (pts_trasa or [])
        s.pietra = sorted({p[2] for p in wszystkie})
        pierwszy = (pts_doj or pts_trasa or [None])[0]
        s.start_z = pierwszy[2] if pierwszy else None
        s.miasto_z_geometrii = miasto_z_pozycji(pierwszy, t.miasta) if pierwszy else None
        for (nazwa, pts) in ((s.dojscie, pts_doj), (s.trasa, pts_trasa)):
            if not pts:
                continue
            if wymaga_liny(pts, liny_znane):
                s.wymaga.add("lina")
                s.wymaga_opis.setdefault("lina", []).append(f"{nazwa} ({len(wymaga_liny(pts, liny_znane))} przejść)")
            if wymaga_lopaty(pts, zasypane):
                s.wymaga.add("lopata")
                s.wymaga_opis.setdefault("lopata", []).append(f"{nazwa} ({len(wymaga_lopaty(pts, zasypane))} dziur)")
        for dod in w.get("wymaga_dodatkowo") or []:
            s.wymaga.add(str(dod))
            s.wymaga_opis.setdefault(str(dod), []).append("tabela (ręcznie)")
        t.spoty[mapa] = s
    t.osierocone = sorted(set(wpisy) - set(mapy))
    return t


# ---------- wybór ----------
def _ekwipunek_lazy(postac):
    cache = {}

    def daj():
        if "v" not in cache:
            e = postac.get("ekwipunek")
            if callable(e):
                try:
                    e = e()
                except Exception:       # noqa: BLE001
                    e = None
            cache["v"] = e if isinstance(e, dict) else {}
        return cache["v"]
    return daj


def _opis_odrzuconych(odrz):
    """Jedno zdanie o odrzuconych: spoty z innych miast / wyłączone policzone, reszta z nazwą i powodem."""
    licz = {"miasto": 0, "auto": 0}
    imienne = []
    for mapa, kod, tekst in odrz:
        if kod in licz:
            licz[kod] += 1
        else:
            imienne.append(f"{mapa} ({tekst})")
    czesci = []
    if licz["miasto"]:
        czesci.append(f"{licz['miasto']} z innych miast")
    if licz["auto"]:
        czesci.append(f"{licz['auto']} wyłączonych w tabeli")
    return "; ".join(imienne + czesci)


def wybierz(postac, zajete=(), historia=(), tabela=None, ziarno=None, korzen=None):
    """Wybór spotu dla postaci.

    postac: {"id", "poz": (x, y, z) z gry, "poziom": int, "ekwipunek": {"lina": True|False|None, "lopata": ...} albo funkcja go zwracająca}.
    zajete: mapy zajęte przez INNE własne boty (cała jaskinia jest wtedy zajęta). historia: mapy poprzednich zmian tej postaci (ostatnia na końcu).
    Zwraca {"mapa", "jaskinia", "powod", "odrzucone": [(mapa, kod, tekst)], "kandydaci": [mapa]} albo
    {"mapa": None, "brak": "dane"|"spot", "powod", "odrzucone"}: "dane" = nie da się ocenić (pozycja/poziom/tabela), "spot" = nic nie pasuje."""
    t = tabela if tabela is not None else wczytaj(korzen)
    id_ = postac.get("id", "?")
    odrz = []

    def brak(rodzaj, powod):
        return {"mapa": None, "brak": rodzaj, "powod": powod, "odrzucone": odrz, "kandydaci": []}

    if t.blad:
        return brak("dane", t.blad)
    poz, poziom = postac.get("poz"), postac.get("poziom")
    if not poz:
        return brak("dane", "pozycja postaci nieznana (brak odczytu z gry)")
    miasto = miasto_z_pozycji(poz, t.miasta)
    if miasto is None:
        return brak("spot", f"pozycja {tuple(poz[:3])} poza znanymi miastami ({', '.join(sorted(t.miasta))}): nie zgaduję spotu")
    if poziom is None:
        return brak("dane", "poziom postaci nieznany (brak odczytu z gry)")
    z = poz[2] if len(poz) > 2 else None
    zaj_jask = {t.jaskinia_mapy(m) for m in zajete}
    ost = t.jaskinia_mapy(historia[-1]) if historia else None
    kand = []
    for nazwa in sorted(t.spoty):
        s = t.spoty[nazwa]
        if not s.auto:
            odrz.append((nazwa, "auto", f"wyłączony w tabeli: {s.powod}"))
        elif s.miasto != miasto:
            odrz.append((nazwa, "miasto", f"miasto {s.miasto}, postać w {miasto}"))
        elif not (s.poziom[0] <= poziom <= s.poziom[1]):
            odrz.append((nazwa, "poziom", f"poziom {poziom} poza {s.poziom[0]}-{s.poziom[1]}"))
        elif s.dojscie and z is not None and z != LEKKIE_Z and not s.z_dowolnego_pietra:
            odrz.append((nazwa, "pietro", f"dojście tylko ze z{LEKKIE_Z}, postać na z{z}"))
        elif s.jaskinia in zaj_jask:
            odrz.append((nazwa, "zajete", "jaskinia zajęta przez inny bot"))
        else:
            kand.append(s)
    # ekwipunek (odczyt leniwy: tylko gdy któryś kandydat czegoś wymaga)
    eq = _ekwipunek_lazy(postac)
    pewne, niepewne = [], []
    for s in kand:
        brakuje, nieznane = [], []
        for przedmiot in sorted(s.wymaga - t.zakladane):
            v = eq().get(przedmiot)
            if v is False:
                brakuje.append(przedmiot)
            elif v is not True:
                nieznane.append(przedmiot)
        if brakuje:
            odrz.append((s.mapa, "ekwipunek", "brak: " + ", ".join(brakuje)))
        elif nieznane:
            niepewne.append((s, nieznane))
        else:
            pewne.append(s)
    nota = ""
    if pewne:
        for s, nz in niepewne:
            odrz.append((s.mapa, "ekwipunek", "nieznane (brak odczytu): " + ", ".join(nz) + "; są pewniejsze spoty"))
        kand = pewne
    elif niepewne:
        kand = [s for s, _ in niepewne]
        nota = " (ekwipunek nieodczytany, jedyne dostępne spoty z wymaganiami: tak samo jak mozg.sprawdz_line, nieznane = start)"
    else:
        kand = []
    # mieszanie
    if ost and any(s.jaskinia != ost for s in kand):
        for s in [s for s in kand if s.jaskinia == ost]:
            odrz.append((s.mapa, "mieszanie", "ta sama jaskinia co poprzednia zmiana"))
        kand = [s for s in kand if s.jaskinia != ost]
    if not kand:
        return brak("spot", f"brak spotu dla {id_}: miasto {miasto}, poziom {poziom}; odrzucone: {_opis_odrzuconych(odrz) or 'nic w tabeli'}")
    ziarno = ziarno if ziarno is not None else f"{date.today().isoformat()}|{id_}"
    rng = random.Random(f"{ziarno}|{id_}|spoty")
    wagi = [max(s.waga, 0.0) for s in kand]
    if not sum(wagi):
        wagi = [1.0] * len(kand)
    wyb = rng.choices(kand, weights=wagi, k=1)[0]
    mieszanie = f", inna jaskinia niż poprzednio ({ost})" if ost else ""
    powod = (f"wybrano {wyb.mapa}: miasto {miasto}, poziom {poziom} w {wyb.poziom[0]}-{wyb.poziom[1]}"
             f"{' (widełki domyślne)' if wyb.poziom_zrodlo == 'domyslne' else ''}, jaskinia {wyb.jaskinia} wolna{mieszanie}"
             f"{', wymaga ' + '+'.join(sorted(wyb.wymaga)) + ' (jest)' if wyb.wymaga and not nota else ''}"
             f"{nota}; wśród {len(kand)} kandydatów: {', '.join(s.mapa for s in kand)}"
             f"{'; odrzucone: ' + _opis_odrzuconych(odrz) if odrz else ''}")
    return {"mapa": wyb.mapa, "jaskinia": wyb.jaskinia, "powod": powod, "odrzucone": odrz, "kandydaci": [s.mapa for s in kand]}


# ---------- ekwipunek (odczyt pamięci gry, tylko CLI / subprocess z RETRONIC_ID) ----------
def ekwipunek_postaci(zapytaj=None):
    """{"lina": True|False|None, "lopata": ...} z jednego odczytu pamięci gry (`kontenery` + `ekwipunek`). Wyjątek/brak odczytu = None."""
    try:
        if zapytaj is None:
            import loot  # noqa: PLC0415
            zapytaj = loot._zapytaj
        odp = zapytaj({"cmd": "kontenery", "ekwipunek": True})
    except Exception:       # noqa: BLE001
        return {"lina": None, "lopata": None}
    try:
        import liny  # noqa: PLC0415
        lina = liny.ma_line(lambda _z: odp)
    except Exception:       # noqa: BLE001
        lina = None
    return {"lina": lina, "lopata": _ma_przedmiot(odp, ID_LOPATA)}


def _ma_przedmiot(odp, id_przedmiotu):
    """Jak liny.ma_line, dla dowolnego ID: True/False albo None (brak odczytu)."""
    if not isinstance(odp, dict) or odp.get("blad"):
        return None
    for k in odp.get("kontenery") or []:
        if any(int(p.get("id", -1)) == id_przedmiotu for p in k.get("przedmioty", [])):
            return True
    eq = odp.get("ekwipunek")
    if isinstance(eq, dict) and any(int((v or {}).get("id", -1)) == id_przedmiotu for v in eq.values()):
        return True
    if eq is None and not odp.get("kontenery"):
        return None
    return False


# ---------- sprawdzenie spójności ----------
def sprawdz(tabela):
    """Lista rozbieżności tabeli (puste = spójna)."""
    t = tabela
    p = []
    if t.blad:
        return [t.blad]
    for m in t.nieopisane:
        p.append(f"mapa {m} jest w mapy.json, a nie ma jej w spoty_nadzorca.json (nadzorca jej nie wybierze)")
    for m in t.osierocone:
        p.append(f"wpis {m} w spoty_nadzorca.json nie ma mapy w mapy.json")
    for nazwa, s in sorted(t.spoty.items()):
        if s.miasto not in t.miasta:
            p.append(f"{nazwa}: miasto {s.miasto!r} nie ma prostokąta w 'miasta'")
        if s.miasto_z_geometrii and s.miasto_z_geometrii != s.miasto:
            p.append(f"{nazwa}: wpisane miasto {s.miasto}, a punkty tras leżą w {s.miasto_z_geometrii}")
        if s.miasto_z_geometrii is None and s.pietra:
            p.append(f"{nazwa}: punkty tras poza prostokątami miast")
        if s.brak_tras:
            p.append(f"{nazwa}: brak plików tras: {', '.join(s.brak_tras)}")
        if s.poziom[0] > s.poziom[1]:
            p.append(f"{nazwa}: widełki poziomu odwrócone {s.poziom}")
    nazwy = sorted(t.miasta)
    for i, a in enumerate(nazwy):
        for b in nazwy[i + 1:]:
            ra, rb = t.miasta[a], t.miasta[b]
            if ra["x"][0] <= rb["x"][1] and rb["x"][0] <= ra["x"][1] and ra["y"][0] <= rb["y"][1] and rb["y"][0] <= ra["y"][1]:
                p.append(f"prostokąty miast {a} i {b} zachodzą na siebie")
    jask = {}
    for nazwa, s in t.spoty.items():
        jask.setdefault(s.jaskinia, set()).add(s.miasto)
    for j, ms in sorted(jask.items()):
        if len(ms) > 1:
            p.append(f"jaskinia {j} jest w kilku miastach: {sorted(ms)}")
    return p


def _tabela_tekst(t):
    wiersze = [("mapa", "miasto", "piętra", "poziom", "wymaga", "auto", "jaskinia", "waga", "potwory")]
    for n, s in sorted(t.spoty.items(), key=lambda kv: (kv[1].miasto or "", kv[0])):
        wiersze.append((n, s.miasto or "?", ",".join(f"z{z}" for z in s.pietra), f"{s.poziom[0]}-{s.poziom[1]}{'*' if s.poziom_zrodlo == 'domyslne' else ''}",
                        "+".join(sorted(s.wymaga)) or "-", "tak" if s.auto else "NIE", s.jaskinia, f"{s.waga:g}", s.potwory or ""))
    szer = [max(len(str(w[i])) for w in wiersze) for i in range(len(wiersze[0]))]
    out = ["  ".join(str(c).ljust(szer[i]) for i, c in enumerate(w)).rstrip() for w in wiersze]
    out.append("")
    out.append("* = widełki domyślne (wg potworów, nie z danych): do przeglądu Karola w dane_tibia/spoty_nadzorca.json")
    return "\n".join(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "tabela"
    if cmd == "ekwipunek":
        print(json.dumps(ekwipunek_postaci()))
        return 0
    t = wczytaj()
    if cmd == "tabela":
        if t.blad:
            print(t.blad)
            return 1
        print(_tabela_tekst(t))
        return 0
    if cmd == "sprawdz":
        problemy = sprawdz(t)
        print("\n".join(problemy) if problemy else f"spoty_nadzorca.json spójny z mapy.json i trasami ({len(t.spoty)} spotów)")
        return 1 if problemy else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
