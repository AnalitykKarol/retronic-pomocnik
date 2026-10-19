#!/usr/bin/env python3
"""Zaplecze okna zarządzania Retronic (spec wtyczka-paska/specs/2026-10-19-retronic-okno.md, faza F1).

Okno (QML) tylko czyta JSON z tego CLI i woła jego polecenia; cała logika i zapis są tutaj. Stdlib, bez efektów
ubocznych poza `ustaw`, `cofnij` i `ratunek-oznacz`. Nic nie wysyła do gry, nie uruchamia ani nie zatrzymuje procesów
(jedyne procesy potomne: `panel.py --json` w `stan`, tylko odczyt).

Wynik: JSON na stdout; sukces `{"ok": true, ...}` i kod 0; błąd `{"ok": false, "blad": "..."}` i kod 1 (błędne użycie: 2).

  stan [--instancja ID]                        wszystkie instancje (główna "" + instancje/<id>), równolegle, każda z limitem czasu;
                                               z --instancja tylko ta jedna (i `panel.py --json` tylko dla niej): okno odświeża
                                               wybraną postać co 2 s, pozostałe co 5 s
  pokretla [--instancja ID]                    meta pokręteł: grupa, typ, zakres, domyślna, bieżąca, opis
  ustaw --instancja ID KLUCZ=WART [...]        zapis do na_zywo.json przez pokretla.waliduj (błąd = zero zapisu)
  cofnij --instancja ID                        przywraca ostatnią zmianę z dziennika okno_cofnij.jsonl
  ratunek [--instancja ID] [--od RRRR-MM-DD]   sygnały ratunku z logi/ratunek-RRRRMMDD.jsonl + etykiety + liczniki;
                                               WSZYSTKIE liczniki (też `najczestszy_kod` i `kody`) liczą z okna --od
                                               (domyślnie ostatnie 7 dni), nie z całej historii
  ratunek-oznacz --instancja ID --id X --falszywy|--prawdziwy   etykieta w logi/ratunek-etykiety.jsonl
  mapy-tryby [--instancja ID]                  mapy.json, tryby.json, ostatnia mapa/tryb instancji

Instancja: "" albo "główna" = główna; inaczej id z instancje/<id>/ (instancja.sprawdz_id).
Zmienne tylko do testów: RETRONIC_OKNO_KATALOG (katalog DANYCH zamiast katalogu skryptu), RETRONIC_OKNO_PROC
(zamiast /proc), RETRONIC_OKNO_TERAZ (epoch zamiast zegara).
"""
import argparse
import ast
import collections
import concurrent.futures as cf
import contextlib
import fcntl
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import tokenize
from pathlib import Path

WLASNY = Path(__file__).resolve().parent
sys.path.insert(0, str(WLASNY))
os.environ.pop("RETRONIC_ID", None)        # okno obsługuje wszystkie instancje; id zawsze jawnie
import instancja  # noqa: E402
import pokretla  # noqa: E402
import ratunek as modul_ratunek  # noqa: E402

PANEL_LIMIT_S = 1.5        # twardy limit jednego `panel.py --json`
CALOSC_LIMIT_S = 1.9       # limit całego `stan` (spec: < ~2 s także dla 10 instancji)
DNI_RATUNKU = 7            # domyślne okno `ratunek` bez --od
NAZWA_GLOWNEJ = "główna"

# --- grupy pokręteł: JAWNA tabela prefiks klucza -> grupa (najdłuższy pasujący prefiks wygrywa; reszta = Zaawansowane) ---
GRUPY = ["Walka i pościg", "Leczenie i runy", "Wyprawa i serwis", "Patrol", "Gracze i PK", "Piętra i dojście",
         "Loot", "Ratunek", "Zaawansowane"]
PREFIKSY_GRUP = {
    "Walka i pościg": ["POSCIG", "POGON", "IGNOROWANIE", "IGNOR", "OBJAZD", "LIMIT", "ATAK", "CZEKAJ", "REAKCJA",
                       "DRUGI", "ODPUSZCZ", "ROZPRAWA"],
    "Leczenie i runy": ["ZDROWIE", "UH", "RUNA", "JEDZENIE", "BLANKI", "ML"],
    "Wyprawa i serwis": ["WYPRAWA", "WYPAD", "WROC", "POCHODNIA", "SERWIS"],
    "Patrol": ["PATROL", "OBECNOSC"],
    "Gracze i PK": ["PK", "PVP", "MIJANIE", "UNIKANIE", "CUDZY", "CZASZKA", "OBSERWATOR", "PATROL_GRACZ"],
    "Piętra i dojście": ["PIETRA", "DOJSCIE", "WPADNIECIE", "DRZWI", "TRASA", "RUCH", "DZIURA", "DZIURY"],
    "Loot": ["LOOT", "KROKI_DO_ZWLOK"],
    "Ratunek": ["RATUNEK"],
}
_PREFIKS_NA_GRUPE = {p: g for g, lista in PREFIKSY_GRUP.items() for p in lista}


class Blad(Exception):
    def __init__(self, komunikat, kod=1, **dodatki):
        super().__init__(komunikat)
        self.komunikat, self.kod, self.dodatki = komunikat, kod, dodatki


# ---------- ścieżki, czas, wspólne ----------
def katalog():
    return Path(os.environ.get("RETRONIC_OKNO_KATALOG") or WLASNY)


def teraz():
    v = os.environ.get("RETRONIC_OKNO_TERAZ")
    return float(v) if v else time.time()


def sciezki(id_):
    kat = katalog()
    return instancja.sciezki(id_, instancja.runtime(f"/run/user/{os.getuid()}"), katalog=kat, gra=kat.parent)


def normalizuj_id(wartosc):
    """'' / 'główna' -> ''; inaczej poprawne id istniejącej instancji."""
    v = (wartosc or "").strip()
    if v in ("", NAZWA_GLOWNEJ):
        return ""
    try:
        v = instancja.sprawdz_id(v)
    except ValueError as e:
        raise Blad(str(e), kod=1)
    if not (katalog() / "instancje" / v).is_dir():
        raise Blad(f"nieznana instancja {v!r} (brak katalogu instancje/{v})")
    return v


def lista_instancji():
    ids = [""]
    kat = katalog() / "instancje"
    if kat.is_dir():
        for p in sorted(kat.iterdir()):
            if not p.is_dir():
                continue
            try:
                i = instancja.sprawdz_id(p.name)
            except ValueError:
                continue                       # _wspolne i śmieci
            if i == p.name:
                ids.append(i)
    return ids


def czytaj_json_dict(sciezka):
    """-> (dict, blad). Brak pliku = ({}, None); uszkodzony / nie-obiekt = ({}, komunikat)."""
    try:
        surowe = Path(sciezka).read_bytes()
    except FileNotFoundError:
        return {}, None
    except OSError as e:
        return {}, f"{Path(sciezka).name}: {e}"
    try:
        d = json.loads(surowe)
    except ValueError as e:
        return {}, f"{Path(sciezka).name}: nieprawidłowy JSON ({e})"
    if not isinstance(d, dict):
        return {}, f"{Path(sciezka).name}: oczekiwano obiektu JSON"
    return d, None


def zapisz_atomowo(plik, tekst):
    plik = Path(plik)
    tmp = plik.with_name(f"{plik.name}.tmp-okno-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tekst)
            f.flush()
            os.fsync(f.fileno())
        if plik.exists():
            shutil.copymode(plik, tmp)
        os.replace(tmp, plik)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


@contextlib.contextmanager
def blokada(sc):
    """Wyłączność na zapisy okna dla instancji (dwa równoległe `ustaw` nie zgubią sobie zmian)."""
    Path(sc.stan).mkdir(parents=True, exist_ok=True)
    with open(Path(sc.stan) / "okno.lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ---------- stałe cavebota (domyślne) i opisy pokręteł ----------
def stale_cavebota():
    """({NAZWA: literał}, {NAZWA: komentarz z linii}) z cavebot.py (ast; bez importu, bez efektów ubocznych).
    Późniejsze przypisanie nadpisuje wcześniejsze (cavebot.py ma kilka stałych dwa razy)."""
    plik = katalog() / "cavebot.py"
    try:
        zrodlo = plik.read_text(encoding="utf-8")
        drzewo = ast.parse(zrodlo)
    except (OSError, SyntaxError, ValueError):
        return {}, {}
    wartosci, komentarze_linii = {}, _komentarze_linii(zrodlo)
    komentarze = {}
    for n in drzewo.body:
        cel, wart = None, None
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            cel, wart = n.targets[0].id, n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            cel, wart = n.target.id, n.value
        if cel is None:
            continue
        try:
            wartosci[cel] = ast.literal_eval(wart)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            continue
        if komentarze_linii.get(n.end_lineno):
            komentarze[cel] = komentarze_linii[n.end_lineno]
    return wartosci, komentarze


def _komentarze_linii(zrodlo):
    """{numer linii: tekst komentarza} (tokenize, więc '#' w napisach nie myli)."""
    wynik = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(zrodlo).readline):
            if tok.type == tokenize.COMMENT:
                wynik[tok.start[0]] = tok.string.lstrip("#").strip()
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return wynik


def opisy_pokretel():
    """{klucz: opis} z komentarzy przy kluczach ZAKRESY/TEKSTY w pokretla.py. Komentarz liczy się tylko, gdy
    w jego linii stoi dokładnie jeden klucz (linia z kilkoma wpisami nie ma jednoznacznego opisu)."""
    zrodlo = Path(pokretla.__file__).read_text(encoding="utf-8")
    kom = _komentarze_linii(zrodlo)
    klucze_linii = collections.defaultdict(list)
    wpisy = []
    for n in ast.parse(zrodlo).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("ZAKRESY", "TEKSTY") for t in n.targets) \
                and isinstance(n.value, ast.Dict):
            for k, v in zip(n.value.keys, n.value.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    wpisy.append((k.value, v.end_lineno))
                    klucze_linii[v.end_lineno].append(k.value)
    return {k: kom[l] for k, l in wpisy if len(klucze_linii[l]) == 1 and kom.get(l)}


def grupa_pokretla(klucz):
    czesci = klucz.split("_")
    for n in range(len(czesci), 0, -1):
        g = _PREFIKS_NA_GRUPE.get("_".join(czesci[:n]))
        if g:
            return g
    return "Zaawansowane"


def calkowite_pokretlo(klucz, domyslne):
    """JEDNA reguła „liczba całkowita czy ułamek” (typ_pokretla i walidacja w cmd_ustaw): zakres z liczb całkowitych
    i domyślna cavebota, która NIE jest float. Domyślna float (np. OGIEN_IGNORUJ_S = 0.0) = pokrętło ułamkowe."""
    a, b = pokretla.ZAKRESY[klucz]
    return isinstance(a, int) and isinstance(b, int) and not isinstance(domyslne.get(klucz), float)


def typ_pokretla(klucz, domyslne):
    if klucz in pokretla.TEKSTY:
        return "tekst"
    if calkowite_pokretlo(klucz, domyslne):
        return "przelacznik" if pokretla.ZAKRESY[klucz] == (0, 1) else "calkowita"
    return "ulamkowa"


def _jsonowa(v):
    return int(v) if isinstance(v, bool) else v


def wartosci_biezace(sc):
    """({klucz: wartość jak ją zobaczy bot}, odrzucone, blad_pliku) z na_zywo.json instancji."""
    dane, blad = czytaj_json_dict(sc.na_zywo)
    ok, bledy = pokretla.waliduj(dane)
    return ok, bledy, blad


def biezaca_wartosc(sc, klucz, domyslne):
    ok, _, _ = wartosci_biezace(sc)
    if klucz in ok:
        return ok[klucz]
    if klucz in domyslne:
        return domyslne[klucz]
    return modul_ratunek.DOMYSLNE.get(klucz)


# ---------- pokretla ----------
def cmd_pokretla(id_):
    sc = sciezki(id_)
    domyslne, kom_cavebota = stale_cavebota()
    opisy = opisy_pokretel()
    biezace, odrzucone, blad_pliku = wartosci_biezace(sc)
    lista = []
    for klucz in [*pokretla.ZAKRESY, *pokretla.TEKSTY]:
        typ = typ_pokretla(klucz, domyslne)
        dom = _jsonowa(domyslne.get(klucz))
        bie = _jsonowa(biezace.get(klucz, dom))
        wpis = {"klucz": klucz, "grupa": grupa_pokretla(klucz), "typ": typ,
                "min": None, "max": None, "domyslna": dom, "biezaca": bie,
                "zmieniona": klucz in biezace and bie != dom,
                "opis": opisy.get(klucz) or kom_cavebota.get(klucz) or ""}
        if typ == "tekst":
            wpis["opcje"] = list(pokretla.TEKSTY[klucz])
        else:
            wpis["min"], wpis["max"] = pokretla.ZAKRESY[klucz]
        lista.append(wpis)
    grupy = [{"nazwa": g, "ile": sum(1 for w in lista if w["grupa"] == g),
              "zmienione": sum(1 for w in lista if w["grupa"] == g and w["zmieniona"])} for g in GRUPY]
    return {"instancja": id_, "plik": str(sc.na_zywo), "plik_istnieje": Path(sc.na_zywo).exists(),
            "blad_pliku": blad_pliku, "odrzucone_w_pliku": odrzucone, "grupy": grupy, "pokretla": lista}


# ---------- ustaw / cofnij ----------
def _parsuj_wartosc(tekst):
    try:
        return json.loads(tekst)
    except ValueError:
        return tekst


DZIENNIK_MAKS = 200        # tyle ostatnich wpisów trzyma okno_cofnij.jsonl


def _dziennik(sc):
    return Path(sc.stan) / "okno_cofnij.jsonl"


def _bot_uzywa(klucz, wartosc):
    """Czy bot użyje tej wartości z na_zywo.json (przechodzi pokretla.waliduj)? Jeśli nie, bot ją ignoruje, więc dla
    `cofnij` taka wartość „przed” jest równoważna brakowi klucza i nie wolno jej odtwarzać."""
    ok, bledy = pokretla.waliduj({klucz: wartosc})
    return klucz in ok and not bledy


def _zapisz_zmiany_pliku(sc, surowe, nowe, kiedy):
    """Kopia .bak-RRRRMMDD-okno (raz dziennie, tylko gdy plik istniał), potem zapis atomowy w formacie bota."""
    plik = Path(sc.na_zywo)
    if surowe is not None:
        bak = plik.with_name(f"{plik.name}.bak-{time.strftime('%Y%m%d', time.localtime(kiedy))}-okno")
        try:
            with open(bak, "xb") as f:
                f.write(surowe)
        except FileExistsError:
            pass
    zapisz_atomowo(plik, json.dumps(nowe, ensure_ascii=False, indent=1))


def _wczytaj_do_zmiany(sc):
    plik = Path(sc.na_zywo)
    try:
        surowe = plik.read_bytes()
    except FileNotFoundError:
        return None, {}
    except OSError as e:
        raise Blad(f"na_zywo.json: {e}")
    try:
        dane = json.loads(surowe)
    except ValueError as e:
        raise Blad(f"na_zywo.json uszkodzony, nic nie zapisano ({e})")
    if not isinstance(dane, dict):
        raise Blad("na_zywo.json: oczekiwano obiektu JSON, nic nie zapisano")
    return surowe, dane


def cmd_ustaw(id_, pary):
    sc = sciezki(id_)
    zadane = {}
    for p in pary:
        if "=" not in p:
            raise Blad(f"oczekiwano KLUCZ=WARTOŚĆ, jest {p!r}", kod=2)
        k, v = p.split("=", 1)
        k = k.strip()
        if not k:
            raise Blad(f"pusty klucz w {p!r}", kod=2)
        if k in zadane:
            raise Blad(f"klucz {k} podany dwa razy; nic nie zapisano")
        zadane[k] = _parsuj_wartosc(v.strip())
    ok, bledy = pokretla.waliduj({k: v for k, v in zadane.items() if not k.startswith("_")})
    bledy += [f"{k}: klucze z _ nie są pokrętłami" for k in zadane if k.startswith("_")]   # waliduj po cichu pomija _klucze
    domyslne, _ = stale_cavebota()
    for k in list(ok):
        if k in pokretla.ZAKRESY:
            if calkowite_pokretlo(k, domyslne):
                if isinstance(ok[k], float) and not ok[k].is_integer():
                    bledy.append(f"{k}={ok[k]}: to pokrętło jest całkowite")
                    del ok[k]
                else:
                    ok[k] = int(ok[k])
    if bledy:
        raise Blad("odrzucono, nic nie zapisano: " + "; ".join(bledy), bledy=bledy)
    with blokada(sc):
        surowe, dane = _wczytaj_do_zmiany(sc)
        zmienione = {k: v for k, v in ok.items() if k not in dane or dane[k] != v or isinstance(dane[k], bool)}
        if not zmienione:
            return {"instancja": id_, "zmienione": {}, "poprzednie": {}, "bez_zmian": sorted(ok)}
        kiedy = teraz()
        wpis = {"czas": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(kiedy)), "epoch": kiedy,
                "przed": {k: dane[k] for k in zmienione if k in dane and _bot_uzywa(k, dane[k])},
                "brak": [k for k in zmienione if k not in dane or not _bot_uzywa(k, dane[k])], "po": zmienione}
        nowe = dict(dane)
        nowe.update(zmienione)
        dz = _dziennik(sc)
        stary_dziennik = dz.read_bytes() if dz.exists() else b""
        stare_linie = [l for l in stary_dziennik.decode("utf-8", errors="replace").splitlines() if l.strip()]
        nowe_linie = [*stare_linie[-(DZIENNIK_MAKS - 1):], json.dumps(wpis, ensure_ascii=False)]     # przycięcie pod blokadą
        try:
            zapisz_atomowo(dz, "".join(l + "\n" for l in nowe_linie))
            _zapisz_zmiany_pliku(sc, surowe, nowe, kiedy)
        except Exception as e:
            with contextlib.suppress(OSError):
                zapisz_atomowo(dz, stary_dziennik.decode("utf-8"))
            raise Blad(f"zapis nie powiódł się, dziennik cofnięty ({e})")
    return {"instancja": id_, "zmienione": zmienione, "poprzednie": {k: dane.get(k) for k in zmienione},
            "kopia": _nazwa_kopii(sc, kiedy)}


def _nazwa_kopii(sc, kiedy):
    p = Path(sc.na_zywo)
    return str(p.with_name(f"{p.name}.bak-{time.strftime('%Y%m%d', time.localtime(kiedy))}-okno"))


def cmd_cofnij(id_):
    sc = sciezki(id_)
    with blokada(sc):
        dz = _dziennik(sc)
        try:
            linie = dz.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            linie = []
        linie = [l for l in linie if l.strip()]
        if not linie:
            raise Blad("brak zmian do cofnięcia")
        try:
            wpis = json.loads(linie[-1])
            przed, brak = dict(wpis["przed"]), list(wpis["brak"])
        except (ValueError, KeyError, TypeError) as e:
            raise Blad(f"dziennik cofania uszkodzony (ostatni wpis): {e}")
        # klucz, którego „przed” nie przechodzi walidacji (stary lub ręcznie edytowany dziennik), jest POMIJANY i
        # zgłoszony w wyniku; reszta wpisu jest cofana (jeden zły klucz nie blokuje cofania na zawsze)
        przywroc, pominiete = {}, []
        for k, v in przed.items():
            ok, bledy = pokretla.waliduj({k: v})
            if k in ok and not bledy:
                przywroc[k] = ok[k]
            else:
                pominiete.append({"klucz": k, "powod": "; ".join(bledy) or "klucz z _ nie jest pokrętłem"})
        surowe, dane = _wczytaj_do_zmiany(sc)
        nowe = dict(dane)
        nowe.update(przywroc)
        for k in brak:
            nowe.pop(k, None)
        kiedy = teraz()
        try:
            _zapisz_zmiany_pliku(sc, surowe, nowe, kiedy)
            reszta = "".join(l + "\n" for l in linie[:-1])
            zapisz_atomowo(dz, reszta)
        except Exception as e:
            raise Blad(f"zapis nie powiódł się ({e})")
    return {"instancja": id_, "przywrocone": przywroc, "pominiete": pominiete, "usuniete": brak, "cofnieta_zmiana": wpis.get("czas"),
            "pozostalo_w_dzienniku": len(linie) - 1}


# ---------- ratunek ----------
WZOR_RATUNKU = re.compile(r"^ratunek-(\d{8})\.jsonl$")
ETYKIETY = "ratunek-etykiety.jsonl"      # nie pasuje do WZOR_RATUNKU (nie jest plikiem sygnałów)
ETYKIETY_DOZWOLONE = ("falszywy", "prawdziwy")


def _epoch_czasu(czas):
    try:
        return time.mktime(time.strptime(czas, "%Y-%m-%d %H:%M:%S"))
    except (TypeError, ValueError):
        return None


def sygnaly_ratunku(sc, od):
    """-> (lista sygnałów od najnowszego, liczba pominiętych linii). `od` = 'RRRR-MM-DD'."""
    od_pliku = od.replace("-", "")
    wynik, pominiete, widziane = [], 0, collections.Counter()
    haiku = {}
    logi = Path(sc.logi)
    pliki = sorted(p for p in logi.glob("ratunek-*.jsonl") if WZOR_RATUNKU.match(p.name)) if logi.is_dir() else []
    for plik in pliki:
        data_pliku = WZOR_RATUNKU.match(plik.name).group(1)
        if data_pliku < od_pliku:
            continue
        try:
            linie = plik.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pominiete += 1
            continue
        for nr, linia in enumerate(linie, 1):
            surowa = linia.strip()
            if not surowa:
                continue
            try:
                rek = json.loads(surowa)
            except ValueError:
                rek = None
            if not isinstance(rek, dict):
                pominiete += 1
                continue
            if rek.get("rekord") == "haiku_cien":            # F2a: odpowiedź Haiku w cieniu, dołączana do sygnału po `id`
                if rek.get("id") is not None and isinstance(rek.get("haiku_cien"), dict):
                    haiku[str(rek["id"])] = rek["haiku_cien"]
                continue
            czas = rek.get("czas") if isinstance(rek.get("czas"), str) else None
            if czas and czas[:10] < od:
                continue
            baza = hashlib.sha1(surowa.encode("utf-8")).hexdigest()[:12]      # stabilny: zależy tylko od treści linii
            widziane[baza] += 1
            id_syg = baza if widziane[baza] == 1 else f"{baza}-{widziane[baza]}"
            wynik.append({"id": id_syg, "czas": czas, "epoch": _epoch_czasu(czas), "kod": rek.get("kod"),
                          "opis": rek.get("opis"), "poz": rek.get("poz"), "stan": rek.get("stan"),
                          "tryb": rek.get("tryb"), "wolan_h": rek.get("wolan_h"), "ponad_limit": rek.get("ponad_limit"),
                          "plik": plik.name, "linia": nr, "dane": rek, "etykieta": None, "etykieta_czas": None})
    for syg in wynik:
        h = haiku.get(str(syg["dane"].get("id"))) if syg["dane"].get("id") is not None else None
        if h is not None:
            syg["dane"] = dict(syg["dane"], haiku_cien=h)
            if isinstance(h.get("zrzut"), str) and h["zrzut"] and "/" in h["zrzut"] and ".." not in h["zrzut"]:
                syg["haiku_zrzut"] = str(Path(sc.logi) / h["zrzut"])
    wynik.sort(key=lambda s: (s["epoch"] or 0, s["plik"], s["linia"]), reverse=True)
    return wynik, pominiete


def etykiety_ratunku(sc):
    """{id sygnału: {etykieta, czas}} — ostatni wpis wygrywa. Uszkodzone linie pomijane."""
    wynik = {}
    try:
        linie = (Path(sc.logi) / ETYKIETY).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return wynik
    for l in linie:
        try:
            r = json.loads(l)
            if isinstance(r, dict) and r.get("id") and r.get("etykieta") in ETYKIETY_DOZWOLONE:
                wynik[r["id"]] = {"etykieta": r["etykieta"], "czas": r.get("czas")}
        except ValueError:
            continue
    return wynik


def liczniki_ratunku(sygnaly, kiedy):
    dzis = time.strftime("%Y-%m-%d", time.localtime(kiedy))
    kody = collections.Counter(s["kod"] for s in sygnaly if s["kod"])
    top = None
    if kody:
        kod, ile = sorted(kody.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        top = {"kod": kod, "ile": ile, "opis": next((s["opis"] for s in sygnaly if s["kod"] == kod), None)}
    return {"dzis": sum(1 for s in sygnaly if (s["czas"] or "")[:10] == dzis),
            "ostatnia_godzina": sum(1 for s in sygnaly if s["epoch"] is not None and kiedy - 3600 <= s["epoch"] <= kiedy),
            "najczestszy_kod": top, "kody": dict(kody),
            "falszywe": sum(1 for s in sygnaly if s["etykieta"] == "falszywy"),
            "prawdziwe": sum(1 for s in sygnaly if s["etykieta"] == "prawdziwy")}


def cmd_ratunek(id_, od=None):
    sc = sciezki(id_)
    kiedy = teraz()
    if od is None:
        od = time.strftime("%Y-%m-%d", time.localtime(kiedy - (DNI_RATUNKU - 1) * 86400))
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", od):
        raise Blad(f"--od: oczekiwano RRRR-MM-DD, jest {od!r}", kod=2)
    sygnaly, pominiete = sygnaly_ratunku(sc, od)
    et = etykiety_ratunku(sc)
    for s in sygnaly:
        if s["id"] in et:
            s["etykieta"], s["etykieta_czas"] = et[s["id"]]["etykieta"], et[s["id"]]["czas"]
    domyslne, _ = stale_cavebota()
    lic = liczniki_ratunku(sygnaly, kiedy)
    lic["limit_h"] = biezaca_wartosc(sc, "RATUNEK_LIMIT_H", domyslne)
    lic["haiku"] = biezaca_wartosc(sc, "RATUNEK_HAIKU", domyslne)
    return {"instancja": id_, "od": od, "katalog_logow": str(sc.logi), "sygnaly": sygnaly, "liczniki": lic,
            "pominiete_linie": pominiete}


def cmd_ratunek_oznacz(id_, id_sygnalu, etykieta):
    if etykieta not in ETYKIETY_DOZWOLONE:
        raise Blad(f"etykieta {etykieta!r}", kod=2)
    sc = sciezki(id_)
    sygnaly, _ = sygnaly_ratunku(sc, "0000-00-00")
    if not any(s["id"] == id_sygnalu for s in sygnaly):
        raise Blad(f"nie ma sygnału {id_sygnalu!r} w logach ratunku tej instancji; nic nie zapisano")
    wpis = {"id": id_sygnalu, "etykieta": etykieta,
            "czas": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(teraz()))}
    with blokada(sc):
        Path(sc.logi).mkdir(parents=True, exist_ok=True)
        with open(Path(sc.logi) / ETYKIETY, "ab") as f:                # tylko dopisanie; pliki sygnałów nietknięte
            f.write((json.dumps(wpis, ensure_ascii=False) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
    return {"instancja": id_, "id": id_sygnalu, "etykieta": etykieta, "czas": wpis["czas"]}


# ---------- mapy i tryby ----------
def ostatni_start(id_):
    plik = katalog() / (f"ostatni_start.{id_}.env" if id_ else "ostatni_start.env")
    wynik = {"mapa": None, "tryb": [], "tryb_surowy": None, "plik": str(plik)}
    try:
        tekst = plik.read_text(encoding="utf-8")
    except OSError:
        return wynik
    for linia in tekst.splitlines():
        try:
            czesci = shlex.split(linia)
        except ValueError:
            continue
        m = re.match(r"(MAPA|TRYB)=(.*)$", czesci[0]) if czesci else None
        if not m:
            continue
        if m[1] == "MAPA":
            wynik["mapa"] = m[2] or None
        else:
            wynik["tryb_surowy"] = m[2]
            wynik["tryb"] = [t for t in m[2].split(",") if t]
    return wynik


def cmd_mapy_tryby(id_):
    kat = katalog()
    mapy_d, blad_m = czytaj_json_dict(kat / "mapy.json")
    tryby_d, blad_t = czytaj_json_dict(kat / "tryby.json")
    mapy = [{"nazwa": n, "opis": (d.get("opis") if isinstance(d, dict) else None) or "",
             "dane": {k: v for k, v in d.items() if k != "opis"} if isinstance(d, dict) else {}}
            for n, d in mapy_d.items() if not n.startswith("_")]
    tryby = []
    for n, d in tryby_d.items():
        if n.startswith("_") or not isinstance(d, dict):
            continue
        pk = d.get("pokretla") if isinstance(d.get("pokretla"), dict) else {}
        tryby.append({"nazwa": n, "opis": d.get("opis") or "", "pokretla": pk, "ile_pokretel": len(pk)})
    ost = ostatni_start(id_)
    ost["mapa_znana"] = ost["mapa"] in {m["nazwa"] for m in mapy} if ost["mapa"] else None
    zn_t = {t["nazwa"] for t in tryby}
    ost["tryby_nieznane"] = [t for t in ost["tryb"] if t not in zn_t]
    return {"instancja": id_, "mapy": mapy, "tryby": tryby, "ostatni": ost,
            "opis_map": mapy_d.get("_opis"), "opis_trybow": tryby_d.get("_opis"),
            "blad_map": blad_m, "blad_trybow": blad_t}


# ---------- stan ----------
SWAY_WZOR = re.compile(r"retronic-sesja(?:-([a-z0-9][a-z0-9_-]{0,23}))?/sway\.conf")
BOT_WZOR = re.compile(r"(^|/)(mozg|cavebot)\.py$")
STRAZNIK_WZOR = re.compile(r"(^|/)straznik\.py$")
HP_WZOR = re.compile(r"HP (\d+)/(\d+)\s+mana (\d+)/(\d+)")


def skan_procesow(proc=None):
    """Jeden przebieg po /proc dla wszystkich instancji: {id: {bot:[{pid,tryb,postac}], straznik:[pid], sway:[pid]}}.
    Tylko odczyt. Instancję procesu python poznaje po RETRONIC_ID w jego środowisku (jak panel.py), sway po ścieżce sway.conf."""
    proc = proc or os.environ.get("RETRONIC_OKNO_PROC") or "/proc"
    wynik = collections.defaultdict(lambda: {"bot": [], "straznik": [], "sway": []})
    moj = os.getpid()
    try:
        wpisy = os.listdir(proc)
    except OSError:
        return wynik
    for w in wpisy:
        if not w.isdigit() or int(w) == moj:
            continue
        try:
            argv = [x.decode(errors="replace") for x in Path(f"{proc}/{w}/cmdline").read_bytes().split(b"\0") if x]
        except OSError:
            continue
        if not argv:
            continue
        nazwa = os.path.basename(argv[0])
        if nazwa == "sway":
            m = SWAY_WZOR.search(" ".join(argv))
            if m:
                wynik[m[1] or ""]["sway"].append(int(w))
            continue
        if not nazwa.startswith("python"):
            continue
        skrypty = [a for a in argv[1:] if BOT_WZOR.search(a) or STRAZNIK_WZOR.search(a)]
        if not skrypty:
            continue
        try:
            surowe = Path(f"{proc}/{w}/environ").read_bytes()
        except OSError:
            continue
        id_ = instancja.id_z_environ(surowe)
        if BOT_WZOR.search(skrypty[0]):
            tryb = os.path.basename(skrypty[0])
            if "--tryb" in argv and argv.index("--tryb") + 1 < len(argv):
                tryb += " " + argv[argv.index("--tryb") + 1]
            postac = next((x[len(b"RETRONIC_POSTAC="):].decode(errors="replace") for x in surowe.split(b"\0")
                           if x.startswith(b"RETRONIC_POSTAC=")), None)
            wynik[id_]["bot"].append({"pid": int(w), "tryb": tryb, "postac": postac})
        else:
            wynik[id_]["straznik"].append(int(w))
    return wynik


def nick_z_logu(sciezka, maks=262144):
    try:
        with open(sciezka, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - maks))
            tekst = f.read().decode(errors="replace")
    except OSError:
        return None
    nazwy = re.findall(r"Connecting to character (.+?) on ", tekst)
    return nazwy[-1] if nazwy else None


def odczyt_panelu(id_):
    """`panel.py --json` instancji (tylko odczyt) z twardym limitem czasu. -> dict albo wyjątek Blad."""
    panel = katalog() / "panel.py"
    try:
        r = subprocess.run([sys.executable, "-I", str(panel), "--json"], capture_output=True, timeout=PANEL_LIMIT_S,
                           env=instancja.srodowisko(id_, bazowe=os.environ), cwd=str(katalog()),
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise Blad(f"panel.py --json przekroczył limit {PANEL_LIMIT_S} s")
    except OSError as e:
        raise Blad(f"panel.py nie wystartował: {e}")
    if r.returncode != 0:
        koniec = r.stderr.decode(errors="replace").strip().splitlines()[-1:] or [""]
        raise Blad(f"panel.py --json: kod {r.returncode} {koniec[0][:160]}")
    try:
        d = json.loads(r.stdout)
    except ValueError:
        raise Blad("panel.py --json: odpowiedź nie jest JSON-em")
    if not isinstance(d, dict):
        raise Blad("panel.py --json: oczekiwano obiektu")
    return d


def pola_z_procesow(w, procesy):
    """Pola `stan` znane już ze skanu procesów (bez żadnego I/O): sesja, klient, bot, nick z RETRONIC_POSTAC."""
    w["sesja"] = bool(procesy["sway"])
    w["klient_pids"] = list(procesy["straznik"])
    w["bot"] = bool(procesy["bot"])
    w["bot_procesy"] = [{"pid": b["pid"], "tryb": b["tryb"]} for b in procesy["bot"]]
    w["nick"] = next((b["postac"] for b in procesy["bot"] if b["postac"]), None)


def pusty_stan(id_):
    return {"id": id_, "nazwa": id_ or NAZWA_GLOWNEJ, "blad": None, "panel": None, "klasa": None, "gracz": None,
            "gra": None, "sesja": None, "bot": None, "bot_procesy": [], "klient_pids": [], "nick": None,
            "mapa": None, "tryb": [], "ratunek_dzis": None}


def stan_instancji(id_, procesy):
    sc = sciezki(id_)
    bledy = []
    w = pusty_stan(id_)

    def krok(opis, f):
        try:
            f()
        except Exception as e:                      # awaria jednego odczytu nie psuje reszty instancji
            bledy.append(f"{opis}: {e}")

    def panel():
        p = odczyt_panelu(id_)
        w["panel"], w["klasa"] = p, p.get("class")
        m = HP_WZOR.search(str(p.get("tooltip") or ""))
        if m:
            w["gracz"] = {"hp": int(m[1]), "max_hp": int(m[2]), "mana": int(m[3]), "max_mana": int(m[4])}

    def procesy_i_pliki():
        w["gra"] = Path(sc.gniazdo).exists()
        pola_z_procesow(w, procesy)
        w["nick"] = w["nick"] or nick_z_logu(sc.log_klienta)

    def ostatni():
        o = ostatni_start(id_)
        w["mapa"], w["tryb"] = o["mapa"], o["tryb"]

    def ratunek_dzis():
        kiedy = teraz()
        dzis = time.strftime("%Y-%m-%d", time.localtime(kiedy))
        sygn, _ = sygnaly_ratunku(sc, dzis)
        w["ratunek_dzis"] = sum(1 for s in sygn if (s["czas"] or "")[:10] == dzis)

    krok("panel", panel)
    krok("procesy", procesy_i_pliki)
    krok("ostatni_start", ostatni)
    krok("ratunek", ratunek_dzis)
    w["blad"] = "; ".join(bledy) or None
    return w


def cmd_stan(id_=None):
    """id_ None = wszystkie instancje; inaczej tylko ta jedna (panel.py --json woła się tylko dla niej)."""
    t0 = time.monotonic()
    ids = lista_instancji() if id_ is None else [id_]
    procesy = skan_procesow()
    puste = {"bot": [], "straznik": [], "sway": []}
    ex = cf.ThreadPoolExecutor(max_workers=min(16, len(ids)))
    try:
        przyszle = {ex.submit(stan_instancji, i, procesy.get(i, puste)): i for i in ids}
        gotowe, _ = cf.wait(przyszle, timeout=max(0.1, CALOSC_LIMIT_S - (time.monotonic() - t0)))
        wynik = []
        for f, i in przyszle.items():
            if f in gotowe and f.exception() is None:
                wynik.append(f.result())
            else:
                powod = f"awaria odczytu: {f.exception()}" if f in gotowe else f"przekroczony limit {CALOSC_LIMIT_S} s"
                w = pusty_stan(i)
                w["blad"] = powod
                pola_z_procesow(w, procesy.get(i, puste))          # bot/sesja/nick już zebrane skanem, bez dodatkowego I/O
                wynik.append(w)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return {"czas": teraz(), "czas_odczytu_s": round(time.monotonic() - t0, 3), "instancje": wynik}


# ---------- CLI ----------
class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Blad(message, kod=2)


def zbuduj_parser():
    p = Parser(prog="okno_api.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="polecenie", required=True, parser_class=Parser)

    def inst(sp, wymagana):
        sp.add_argument("--instancja", default=None if wymagana else "", help='id instancji; "" albo "główna" = główna')
    sp = sub.add_parser("stan"); inst(sp, True)         # tu --instancja opcjonalne (brak = wszystkie)
    sp = sub.add_parser("pokretla"); inst(sp, False)
    sp = sub.add_parser("ustaw"); inst(sp, True); sp.add_argument("pary", nargs="+", metavar="KLUCZ=WART")
    sp = sub.add_parser("cofnij"); inst(sp, True)
    sp = sub.add_parser("ratunek"); inst(sp, False); sp.add_argument("--od", default=None, metavar="RRRR-MM-DD")
    sp = sub.add_parser("ratunek-oznacz"); inst(sp, True); sp.add_argument("--id", required=True, dest="sygnal")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--falszywy", action="store_true"); g.add_argument("--prawdziwy", action="store_true")
    sp = sub.add_parser("mapy-tryby"); inst(sp, False)
    return p


def wykonaj(a):
    c = a.polecenie
    if c == "stan":
        return cmd_stan(None if a.instancja is None else normalizuj_id(a.instancja))
    if getattr(a, "instancja", None) is None:
        raise Blad(f"{c}: wymagane --instancja ID (\"\" albo \"{NAZWA_GLOWNEJ}\" = główna)", kod=2)
    id_ = normalizuj_id(a.instancja)
    if c == "pokretla":
        return cmd_pokretla(id_)
    if c == "ustaw":
        return cmd_ustaw(id_, a.pary)
    if c == "cofnij":
        return cmd_cofnij(id_)
    if c == "ratunek":
        return cmd_ratunek(id_, a.od)
    if c == "ratunek-oznacz":
        return cmd_ratunek_oznacz(id_, a.sygnal, "falszywy" if a.falszywy else "prawdziwy")
    if c == "mapy-tryby":
        return cmd_mapy_tryby(id_)
    raise Blad(f"nieznane polecenie {c}", kod=2)


def main(argv=None):
    try:
        a = zbuduj_parser().parse_args(argv)
        wynik = {"ok": True, **wykonaj(a)}
        print(json.dumps(wynik, ensure_ascii=False))
        return 0
    except Blad as e:
        print(json.dumps({"ok": False, "blad": e.komunikat, **e.dodatki}, ensure_ascii=False))
        return e.kod
    except Exception as e:                            # nic nie ucieka jako traceback: okno parsuje tylko JSON
        print(json.dumps({"ok": False, "blad": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
