"""26.10 (decyzja Karola): po ZGONIE postaci stan obrony przed PK ma się ZAWSZE resetować (pokrętło PK_RESET_PO_ZGONIE).

Przypadek: Odchyd zginął 07:33 (gracz „Ogr”, Kazordoon), odrodził się w Edronie, a bot po restarcie o 07:45 miał jeszcze w
wrogowie.json `karencja_do` (30 min) i zapisaną wyprawę PK (`wyprawa_stan.json`: potrzeby.pk, aktywna) -> „karencja po restarcie”,
ucieczka do depo, powrót na spot przez miasto i STOP. Tu: czysta logika rozpoznania „zginęliśmy” z DANYCH NA DYSKU (bot wstaje po
zgonie jako nowy proces, więc pamięć starego procesu nie istnieje). Cavebot (cavebot.py) ma tylko wołać i wykonać reset; lista
wrogów (nicki) NIE jest tu ruszana.

HEURYSTYKA „zginęliśmy, zanim wystartował ten proces” (wszystkie warunki naraz; brak pewności = False, reset NIE następuje):
  1. teraz postać żyje (HP > 0 w pierwszym ważnym odczycie po starcie),
  2. KOŃCÓWKA telemetrii (instancje/<id>/logi/telemetria-*.jsonl, ostatnie próbki wszystkich procesów) to seria próbek
     z HP == 0 (>= PK_RESET_PROBEK próbek i >= PK_RESET_ZGON_S s trwania, czyli nie pojedynczy zły odczyt) ALBO ostatnie zdarzenie
     to `smierc` (SMIERC_STOP potwierdził zgon),
  3. pozycja teraz jest „po respawnie”: inne piętro albo >= SMIERC_SKOK pól od ostatniej pozycji serii HP 0 (martwa postać
     stoi tam, gdzie zginęła; odrodzona jest w świątyni, więc skok; żywa postać z tego samego miejsca po prostu nie zginęła),
  4. ostatnia próbka nie starsza niż PK_RESET_WIEK_H (domyślnie 12 h; starsze = nie wiemy, co się działo).
Zapasowe źródło: instancje/<id>/ostatnie.json (hp == 0, max_hp > 0, ta sama reguła skoku), tylko gdy zapis jest sprzed startu
tego procesu (Pisarz tego procesu mógł go już nadpisać stanem po respawnie).
GRANICE (świadomie): (a) proces zabity zanim zapisał próbkę HP 0 (ostatnia próbka ma np. HP 11%) = brak pewności = BRAK resetu,
karencję zdejmuje wtedy Karol (`obrona_pk.py --zeruj-karencje`); (b) zgon, po którym postać jest nadal martwa (HP 0 teraz) nie
resetuje przy starcie (reset zrobi pętla bota, gdy HP wróci, i tak samo przy kolejnym starcie); (c) alarm PK w innym mieście niż
obecne NIE jest dowodem zgonu (ręczny przelot/łódź, relog w innym miejscu) i nie jest używany; (d) telemetria wyłączona
(RETRONIC_TELEMETRIA=0) = brak danych = brak resetu; (e) wynik liczony raz na proces (pamięć modułu), kolejne obiegi go nie zmieniają.
Tylko stdlib, zero wejścia/wyjścia gry."""
import json
import time
from pathlib import Path

PK_RESET_PROBEK = 3          # tyle próbek z HP == 0 z rzędu (koniec telemetrii) potwierdza zgon (jak SMIERC_ODCZYTY)
PK_RESET_ZGON_S = 8.0        # s: tyle musi trwać seria HP == 0 (pojedyncze złe odczyty trwają krócej)
PK_RESET_WIEK_H = 12.0       # h: starsza ostatnia próbka = nie rozstrzygamy
SMIERC_SKOK = 8              # pól: skok pozycji uznawany za respawn (zgodnie z cavebot.SMIERC_SKOK; cavebot przekazuje własną wartość)
TAIL_BAJTOW = 600_000        # ile z końca pliku telemetrii czytamy (próbka ma kilkaset bajtów)
_START_WALL = time.time()    # moment załadowania modułu ~ start procesu bota (ostatnie.json nadpisane później nie liczy się)
_WYNIK = None                # (bool, opis) policzone raz na proces


def reset_pamieci():
    """Tylko testy: wyczyść wynik policzony dla procesu."""
    global _WYNIK, _START_WALL
    _WYNIK = None
    _START_WALL = time.time()


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def skok_pozycji(a, b, prog):
    """Inne piętro albo odległość (Chebyshev) >= prog."""
    return a[2] != b[2] or _cheb(a, b) >= prog


def rekordy_ogon(katalog, tail_bajtow=TAIL_BAJTOW, max_plikow=2):
    """Rekordy `probka`/`smierc` z końca najnowszych plików telemetria-*.jsonl, rosnąco po t (bez rotowanych .gz itp.)."""
    wynik = []
    try:
        pliki = sorted(p for p in Path(katalog).glob("telemetria-*.jsonl") if p.is_file())
    except OSError:
        return wynik
    for p in reversed(pliki[-max_plikow:]):
        czesc = []
        try:
            with p.open("rb") as f:
                rozm = f.seek(0, 2)
                if rozm > tail_bajtow:
                    f.seek(rozm - tail_bajtow)
                    f.readline()                          # ucięta pierwsza linia
                else:
                    f.seek(0)
                for b in f:
                    if b'"probka"' not in b and b'"smierc"' not in b:
                        continue
                    try:
                        r = json.loads(b)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and r.get("typ") in ("probka", "smierc") and isinstance(r.get("t"), (int, float)):
                        czesc.append(r)
        except OSError:
            continue
        wynik = czesc + wynik                             # starszy plik przed nowszym
        if any(r.get("typ") == "probka" and (r.get("hp") or 0) > 0 for r in czesc):
            break                                         # w tym pliku jest już żywa próbka: dalej wstecz nie trzeba
    wynik.sort(key=lambda r: r["t"])
    return wynik


def _poz(r):
    p = r.get("poz")
    if isinstance(p, (list, tuple)) and len(p) >= 3:
        try:
            return (int(p[0]), int(p[1]), int(p[2]))
        except (TypeError, ValueError):
            return None
    return None


def zgon_z_telemetrii(rek, poz, hp_teraz, teraz_wall, skok=SMIERC_SKOK, probek=PK_RESET_PROBEK,
                      min_s=PK_RESET_ZGON_S, wiek_h=PK_RESET_WIEK_H):
    """(True/False, opis). `rek` = rekordy_ogon (rosnąco). Patrz nagłówek modułu: wszystkie warunki naraz albo False."""
    if hp_teraz is None or hp_teraz <= 0:
        return False, "postać teraz nie żyje albo HP nieodczytane"
    if not rek:
        return False, "brak telemetrii z poprzedniego procesu"
    ost = rek[-1]
    if teraz_wall - float(ost["t"]) > wiek_h * 3600.0:
        return False, f"ostatnia próbka sprzed {(teraz_wall - float(ost['t'])) / 3600:.1f} h (limit {wiek_h:.0f})"
    poz = (int(poz[0]), int(poz[1]), int(poz[2]))
    if ost.get("typ") == "smierc":
        mp = _poz(ost) or None
        return True, f"ostatnie zdarzenie telemetrii: smierc ({time.strftime('%H:%M:%S', time.localtime(ost['t']))}, poz {mp})"
    seria = []
    for r in reversed(rek):
        if r.get("typ") != "probka":
            continue
        if r.get("hp") is None or r.get("hp") > 0:
            break
        seria.append(r)
    if not seria:
        return False, "ostatnia próbka z HP > 0 (poprzedni proces nie widział zgonu)"
    trwanie = float(seria[0]["t"]) - float(seria[-1]["t"])
    if len(seria) < probek or trwanie < min_s:
        return False, f"seria HP 0 za krótka ({len(seria)} próbek, {trwanie:.1f} s; wymagane {probek} i {min_s:.0f} s)"
    mp = _poz(seria[0])
    if mp is None:
        return False, "brak pozycji w próbce HP 0"
    if not skok_pozycji(mp, poz, skok):
        return False, f"brak skoku pozycji (martwa {mp}, teraz {poz}): to nie respawn"
    return True, (f"seria HP 0 ({len(seria)} próbek, {trwanie:.0f} s, koniec {time.strftime('%H:%M:%S', time.localtime(seria[0]['t']))}) "
                  f"w {mp}, teraz żywa w {poz}")


def zgon_z_ostatnie(plik, poz, hp_teraz, teraz_wall, skok=SMIERC_SKOK, wiek_h=PK_RESET_WIEK_H, przed=None):
    """Zapasowo: ostatnie.json (hp == 0 przy max_hp > 0, skok pozycji). Zapis musi być sprzed `przed` (domyślnie start procesu)."""
    if hp_teraz is None or hp_teraz <= 0:
        return False, "postać teraz nie żyje albo HP nieodczytane"
    try:
        d = json.loads(Path(plik).read_text())
    except (OSError, ValueError):
        return False, "brak ostatnie.json"
    if not isinstance(d, dict) or not d.get("max_hp") or d.get("hp") is None or d.get("hp") > 0:
        return False, "ostatnie.json bez HP 0"
    zapis = d.get("zapisano")
    if not isinstance(zapis, (int, float)) or zapis >= (przed if przed is not None else _START_WALL):
        return False, "ostatnie.json zapisany po starcie tego procesu"
    if teraz_wall - zapis > wiek_h * 3600.0:
        return False, "ostatnie.json zbyt stary"
    mp = _poz({"poz": d.get("poz")})
    if mp is None or not skok_pozycji(mp, (int(poz[0]), int(poz[1]), int(poz[2])), skok):
        return False, "ostatnie.json: brak skoku pozycji"
    return True, f"ostatnie.json: HP 0 w {mp}, teraz żywa w {tuple(poz)}"


def zgon_przed_startem(katalog_logi, plik_ostatnie, poz, hp_teraz, teraz_wall=None, skok=SMIERC_SKOK):
    """Jedno rozstrzygnięcie na proces (pamięć modułu), liczone przy pierwszym ważnym odczycie (HP > 0). -> (bool, opis)."""
    global _WYNIK
    if _WYNIK is not None:
        return _WYNIK
    if hp_teraz is None or hp_teraz <= 0 or poz is None:
        return False, "HP/pozycja nieważne: odłożone"          # bez zapamiętania: ocena przy kolejnym obiegu
    t = time.time() if teraz_wall is None else teraz_wall
    wyn = zgon_z_telemetrii(rekordy_ogon(katalog_logi), poz, hp_teraz, t, skok=skok)
    if not wyn[0] and plik_ostatnie is not None:
        w2 = zgon_z_ostatnie(plik_ostatnie, poz, hp_teraz, t, skok=skok)
        if w2[0]:
            wyn = w2
    _WYNIK = wyn
    return wyn
