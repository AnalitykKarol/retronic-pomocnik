"""Wpisy "widmo" na liście stworów/graczy czytanej z pamięci gry (rdzen.py `stwory`).

Dlaczego to osobny moduł: lista z pamięci nie mówi, czy wpis to realna widoczna postać. 19.10 w Edron (PZ) log
miał graczy na tym samym polu co bot i po kilku graczy na jednym polu. Rdzeń nie daje WIEKU wpisu ani flagi
widoczności (pola odczytywane: id, nazwa, x, y, z, hp, kierunek, ramki; patrz rdzen._skanuj_stwory), więc nie
da się odróżnić "stary wpis" od "realnego gracza przechodzącego przez nas w PZ". Tu stosujemy tylko kryteria
GEOMETRYCZNE, które da się uzasadnić z samej listy:

  1. NA_POLU_BOTA: obcy gracz na dokładnie tym polu (x, y, z), na którym stoi bot. Nie może zająć ani zablokować
     żadnego pola do marszu (my na nim stoimy) i nie jest "obcym graczem obok" w sensie oceny odległości.
  2. DUPLIKAT_POLA: kilku obcych graczy na dokładnie tym samym polu (x, y, z). Do ocen zostaje JEDEN
     reprezentant (groźny przed zwykłym, potem najmniejsze id = stabilny wybór), reszta dostaje `widmo`.

Wpis NIGDY nie jest usuwany z danych: dostaje tylko pole `widmo` (powód). Kto ocenia ZAJĘTOŚĆ pól albo "blokujących"
graczy (marsz, serwis, Mijanie/unikanie), pomija wpisy z `widmo` (bez_widm / `not s.get("widmo")`).
Ścieżki bezpieczeństwa (PK/czaszki, GM, alarm, stan dla modelu) czytają listę z stwory() w całości i `widmo`
ignorują: filtr ich nie dotyczy.

Piętra: oznacz() nie zmienia reguły pięter; każdy konsument zajętości i tak porównuje z == piętro postaci
(patrz testy/test_widma.py), a "pole" w kryteriach to zawsze trójka (x, y, z).
"""
import os

NA_POLU_BOTA = "na_polu_bota"
DUPLIKAT_POLA = "duplikat_pola"
LOG_CO_S = 120.0          # s: ten sam (nick, powód) w logu najwyżej raz na tyle


def domyslnie_wlaczone():
    """Moduły poza cavebotem (serwis): RETRONIC_STWORY_WIDMA=0 = stare zachowanie."""
    return os.environ.get("RETRONIC_STWORY_WIDMA", "1") != "0"


def _pole(s):
    try:
        return (int(s["x"]), int(s["y"]), int(s["z"]))
    except (KeyError, TypeError, ValueError):
        return None


def _pole_bota(wlasne, poz):
    """Pole bota w tym samym odczycie (własny wpis); przy braku albo duplikacie (widmo po relogu) pozycja `poz`."""
    if len(wlasne) == 1:
        return _pole(wlasne[0])
    if poz is not None and len(poz) >= 3:
        p = (int(poz[0]), int(poz[1]), int(poz[2]))
        if not wlasne or any(_pole(w) == p for w in wlasne):
            return p
    return None


def oznacz(lista, nick, poz=None, wazny=None):
    """Oznacza w miejscu wpisy-widma (`s["widmo"] = powód`), niczego nie usuwa. Zwraca listę oznaczonych.
    nick: nazwa postaci bota; poz: (x, y, z) z osobnego odczytu (tylko gdy lista nie ma własnego wpisu);
    wazny(s) -> True: wpis, który ma zostać reprezentantem grupy (np. groźny gracz: GM/czaszka)."""
    for s in lista:
        s.pop("widmo", None)
    gracze = [s for s in lista if s.get("gracz")]
    wlasne = [s for s in gracze if s.get("nazwa") == nick]
    ja = _pole_bota(wlasne, poz)
    wynik, grupy = [], {}
    for s in gracze:
        if s.get("nazwa") == nick:
            continue
        p = _pole(s)
        if p is None:
            continue
        if ja is not None and p == ja:
            s["widmo"] = NA_POLU_BOTA
            wynik.append(s)
            continue
        grupy.setdefault(p, []).append(s)
    for g in grupy.values():
        if len(g) < 2:
            continue
        rep = min(g, key=lambda s: (0 if wazny is not None and wazny(s) else 1, s.get("id") or 0))
        for s in g:
            if s is not rep:
                s["widmo"] = DUPLIKAT_POLA
                wynik.append(s)
    return wynik


def bez_widm(lista):
    """Lista bez wpisów oznaczonych `widmo`; gdy nie ma żadnego, ta sama lista (bez kopii)."""
    if not lista or not any(s.get("widmo") for s in lista):
        return lista
    return [s for s in lista if not s.get("widmo")]


def loguj(wynik, log, teraz, pamiec):
    """Rzadki log oznaczonych wpisów: najwyżej raz na LOG_CO_S na (nick, powód). `pamiec`: dict w obiekcie wołającym."""
    for s in wynik:
        klucz = (s.get("nazwa"), s.get("widmo"))
        if teraz - pamiec.get(klucz, float("-inf")) < LOG_CO_S:
            continue
        pamiec[klucz] = teraz
        if len(pamiec) > 200:
            for k in [k for k, t in pamiec.items() if teraz - t > LOG_CO_S]:
                del pamiec[k]
        log(f"Widmo: gracz {s.get('nazwa')} ({s.get('widmo')}) na ({s.get('x')},{s.get('y')},{s.get('z')}): "
            f"nie liczę go do zajętości pól ani do oceny graczy; PK/GM nadal go widzą.")
