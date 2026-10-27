#!/usr/bin/env python3
"""Wspólna ocena flagi „zostań w depo” z planu postaci (instancje/_wspolne/plan_postaci.json). Tylko stdlib; używają jej
refill_auto.py (bot, czekacz refillu), plan_postaci.py i nadzor.py, żeby wszyscy czytali tę samą regułę.

Pola wpisu postaci (24.10, Karol: „invincible i dawajkesh mają zrobić po 2 bp UH-ów, zakończyć i wylogować się w depo”):
  "zostan_w_depo": true                  (23.10) od razu po dojściu do depo: bez refillu, bez wznowienia, postać stoi
  "zostan_w_depo_po_refillach": N        (24.10) to samo, ale DOPIERO po N refillach liczonych od chwili `zostan_w_depo_od`;
                                        wcześniej postać żyje jak bez flagi (refill, powrót na spot). Gdy podane, `zostan_w_depo` jest ignorowane.
  "zostan_w_depo_od": "RRRR-MM-DD GG:MM:SS"   (24.10) od kiedy liczą się refille (brak = wszystkie zapisane)
  "zostan_w_depo_powod": "..."
  "wyloguj_w_depo": true                (24.10) nadzorca wylogowuje postać stojącą w depo ze STOP przy uzbrojonej fladze (wyloguj.sh), zamiast czekać
Licznik refilli: instancje/<id>/refille.json {"t": [epoch, ...]} — dopisuje `refill_auto.czekaj` w chwili, gdy refill.sh --tlo przyjął zlecenie,
ale TYLKO gdy powodem wyprawy do depo były blanki (`depo_start_powody` zawiera "blanki", także cap+blanki); powrót po samym cap, po jedzeniu, po WROC (reczny)
i po PK nie liczy się (24.10, przegląd 2bp). Ręczny `./refill.sh` (guzik) NIE jest liczony.
24.10 (Karol ~10:00: „powrót przy braku capa: zamiana na pc i powrót, aż do pełnego bp run”): wyprawa z powodem WYŁĄCZNIE `cap` (`tylko_cap`) nie zatrzymuje
w depo (także przy `zostan_w_depo` i uzbrojonym `..._po_refillach`), nie uzbraja flagi i kończy się refillem `bank,wyjscie` (refill_auto.czekaj).

25.10 (Karol: „ma być jako default, że postacie wracają do miasta do depo i robią loga i czekają na mnie”): klucz NAJWYŻSZEGO poziomu planu
  "domyslne": {"wlaczone": true, "zostan_w_depo": true, "wyloguj_w_depo": true, "zostan_w_depo_powod": "..."}
daje WSZYSTKIM postaciom (także bez wpisu w „postacie”) te pola, gdy wpis postaci ich sam nie ustawia; pole we wpisie postaci (także `false`,
także `zostan_w_depo_po_refillach`) wygrywa z domyślnym. WŁĄCZNIK: `wlaczone` musi być dokładnie `true`; brak klucza „domyslne”, `wlaczone` false/brak albo błędny
kształt = domyślne WYŁĄCZONE (zachowanie jak przed 25.10). Po włączeniu `zostan_w_depo` i `wyloguj_w_depo` są domyślnie true."""
import json
import os
import time
from datetime import datetime
from pathlib import Path

KLUCZ_DOMYSLNE = "domyslne"
POLA_DOMYSLNE = ("zostan_w_depo", "zostan_w_depo_powod", "wyloguj_w_depo")
POWOD_DOMYSLNY = "domyślnie (plan_postaci.json „domyslne”): wrócona do depo postać zostaje, wylogowana, czeka na Karola"
PLIK_REFILLE = "refille.json"
PLIK_WYPRAWY = "wyprawa_stan.json"
PLIK_SPOT_GRACZ_DEPO = "spot_gracz_depo.json"   # 26.10: instancje/<id>/, nadzorca zapisuje przy powrocie do miasta z powodu graczy (spot_gracz.py)
SPOT_GRACZ_DEPO_WAZNE_S = 12 * 3600.0           # znacznik starszy niż 12 h nie trzyma postaci w depo
SWIEZOSC_WYPRAWY_S = 3600.0         # stan wyprawy starszy niż 1 h nie mówi nic o BIEŻĄCYM depo (np. Stanowisko woła refill bez wyprawy)
MAKS_WPISOW = 20
FMT = "%Y-%m-%d %H:%M:%S"


class Zostan:
    """Odczyt pól flagi z jednego wpisu postaci. `flaga` = skonfigurowana (bez względu na licznik refilli)."""

    def __init__(self):
        self.flaga = False
        self.po_refillach = 0           # 0 = od razu; N >= 1 = po N refillach od `od_ts`
        self.od_ts = None
        self.od = ""
        self.powod = ""
        self.wyloguj = False
        self.blad = None
        self.z_domyslnych = False       # flaga pochodzi z `domyslne` planu, nie z wpisu postaci


def domyslne(plan_dict):
    """Domyślne pola „zostań w depo” z SUROWEGO planu (dict z pliku) -> (dom, blad). `dom` = {"zostan_w_depo", "wyloguj_w_depo", "zostan_w_depo_powod"}
    tylko gdy `domyslne.wlaczone` jest dokładnie True; inaczej None (wyłączone). `blad` = tekst, gdy klucz jest, ale ma zły kształt (domyślne wtedy wyłączone)."""
    d = plan_dict.get(KLUCZ_DOMYSLNE) if isinstance(plan_dict, dict) else None
    if d is None:
        return None, None
    if not isinstance(d, dict):
        return None, f"„{KLUCZ_DOMYSLNE}” musi być obiektem, jest {type(d).__name__} (domyślne wyłączone)"
    w = d.get("wlaczone", False)
    if not isinstance(w, bool):
        return None, f"{KLUCZ_DOMYSLNE}.wlaczone musi być true/false, jest {w!r} (domyślne wyłączone)"
    for k in ("zostan_w_depo", "wyloguj_w_depo"):
        if k in d and not isinstance(d[k], bool):
            return None, f"{KLUCZ_DOMYSLNE}.{k} musi być true/false, jest {d[k]!r} (domyślne wyłączone)"
    if not w:
        return None, None
    return {"zostan_w_depo": bool(d.get("zostan_w_depo", True)), "wyloguj_w_depo": bool(d.get("wyloguj_w_depo", True)),
            "zostan_w_depo_powod": str(d.get("zostan_w_depo_powod") or POWOD_DOMYSLNY)}, None


def parsuj(pc, dom=None):
    """Odczyt flagi z wpisu postaci `pc`; `dom` (z `domyslne()`) uzupełnia pola, których wpis nie ma. `pc` None = postać bez wpisu (tylko domyślne)."""
    z = Zostan()
    if pc is None and dom:
        pc = {}
    if not isinstance(pc, dict):
        return z
    wlasne = {k for k in POLA_DOMYSLNE if k in pc}
    if dom:
        pc = {**dom, **pc}
    z.powod = str(pc.get("zostan_w_depo_powod") or "")
    z.wyloguj = bool(pc.get("wyloguj_w_depo"))
    if "zostan_w_depo_po_refillach" not in pc:
        z.flaga = bool(pc.get("zostan_w_depo"))
        z.z_domyslnych = bool(dom and z.flaga and "zostan_w_depo" not in wlasne)
        return z
    n = pc.get("zostan_w_depo_po_refillach")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        z.blad = f"zostan_w_depo_po_refillach musi być liczbą całkowitą >= 1, jest {n!r} (flaga zostan_w_depo wyłączona)"
        return z
    if pc.get("zostan_w_depo_od") not in (None, ""):
        try:
            z.od = str(pc["zostan_w_depo_od"])
            z.od_ts = datetime.strptime(z.od, FMT).timestamp()
        except (ValueError, TypeError):
            z.blad = f"zostan_w_depo_od={pc.get('zostan_w_depo_od')!r}: oczekiwano „RRRR-MM-DD GG:MM:SS” (flaga zostan_w_depo wyłączona)"
            z.od_ts = None
            return z
    z.flaga, z.po_refillach = True, n
    return z


def czytaj_refille(stan_dir):
    """Posortowana lista epoch-ów refilli instancji; brak / uszkodzony plik = []."""
    try:
        d = json.loads((Path(stan_dir) / PLIK_REFILLE).read_text(encoding="utf-8"))
        t = d.get("t") if isinstance(d, dict) else None
        return sorted(float(x) for x in t if isinstance(x, (int, float)) and not isinstance(x, bool)) if isinstance(t, list) else []
    except (OSError, ValueError):
        return []


def zapisz_refill(stan_dir, t):
    """Dopisuje refill (atomowo: tmp + replace). Błąd zapisu nie przerywa niczego. -> True/False."""
    p = Path(stan_dir) / PLIK_REFILLE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        lista = (czytaj_refille(stan_dir) + [float(t)])[-MAKS_WPISOW:]
        tmp = p.with_name(PLIK_REFILLE + ".tmp")
        tmp.write_text(json.dumps({"t": [round(x, 1) for x in lista]}))
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def powody_depo(stan_dir, teraz=None):
    """Powody ostatniej wyprawy do depo (`depo_start_powody` z wyprawa_stan.json, np. ["cap"], ["blanki"], ["cap", "blanki"], ["reczny"]) albo None,
    gdy stanu brak / jest uszkodzony / nie dotyczy bieżącego depo: wyprawa trwa (`aktywna`) albo skończyła się w depo (`wynik` depo-podobny, `zapis_wall`/`t_wall`
    nie starsze niż SWIEZOSC_WYPRAWY_S). Bot zapisuje to przy starcie każdej wyprawy do depo (wyprawa.py `_start_wyprawa`), a `_stan_koniec` tego nie czyści."""
    teraz = time.time() if teraz is None else teraz
    try:
        d = json.loads((Path(stan_dir) / PLIK_WYPRAWY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("depo_start_powody"), list):
        return None
    if not d.get("aktywna"):
        t = d.get("zapis_wall") if isinstance(d.get("zapis_wall"), (int, float)) else d.get("t_wall")
        if not isinstance(t, (int, float)) or isinstance(t, bool) or not 0 <= teraz - t < SWIEZOSC_WYPRAWY_S:
            return None
    return [str(p) for p in d["depo_start_powody"]]


def tylko_cap(stan_dir, teraz=None):
    """Bieżące depo jest z powodu WYŁĄCZNIE capa (24.10): refill = bank + wyjście, bez depo; flaga `zostan_w_depo` go nie zatrzymuje."""
    return powody_depo(stan_dir, teraz) == ["cap"]


def liczy_sie_do_licznika(stan_dir, teraz=None):
    """Refill po tym depo liczy się do `zostan_w_depo_po_refillach` tylko, gdy powodem były blanki (także razem z cap)."""
    return "blanki" in (powody_depo(stan_dir, teraz) or ())


def refille_od_wpisu(z, stan_dir):
    return [t for t in czytaj_refille(stan_dir) if z.od_ts is None or t >= z.od_ts]


def uzbrojona(z, stan_dir, start_bota=None, wymagaj_startu=False):
    """Czy flaga działa TERAZ. Tryb „od razu”: gdy skonfigurowana. Tryb „po N refillach”: gdy jest >= N refilli od wpisu; z `wymagaj_startu`
    (nadzorca) dodatkowo bot musi być wystartowany PO N-tym refillu (`start_bota` = epoch startu bieżącego bota) — w trakcie samego refillu postać
    stoi w depo ze STOP bez bota i nie wolno jej wtedy uznać za „zostaje”."""
    if not z.flaga:
        return False
    if not z.po_refillach:
        return True
    r = refille_od_wpisu(z, stan_dir)
    if len(r) < z.po_refillach:
        return False
    if wymagaj_startu:
        return start_bota is not None and start_bota > r[z.po_refillach - 1]
    return True


# ---------- 26.10: powrót do miasta po spotkaniach graczy (spot_gracz.py): postać ZOSTAJE w depo do decyzji ----------
def spot_gracz_depo(stan_dir, teraz=None, start_bota=None):
    """Powód (tekst) albo None: nadzorca zlecił powrót do miasta, bo na spocie nie było już wolnego spotu przy graczach (znacznik `spot_gracz_depo.json`).
    Postać po powrocie stoi w depo (jak przy `zostan_w_depo`: bez auto-refillu i bez startu na spot), dopóki Karol/plan nie podejmie decyzji. Znacznik wygasa
    po SPOT_GRACZ_DEPO_WAZNE_S i traci ważność, gdy bot wystartował PO jego zapisie (`start_bota` = epoch startu bieżącego bota, jeśli znany)."""
    teraz = time.time() if teraz is None else teraz
    try:
        d = json.loads((Path(stan_dir) / PLIK_SPOT_GRACZ_DEPO).read_text(encoding="utf-8"))
        t = float(d["t"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not 0 <= teraz - t < SPOT_GRACZ_DEPO_WAZNE_S:
        return None
    if start_bota is not None and start_bota > t:
        return None
    return str(d.get("powod") or "powrót do miasta po spotkaniach graczy (brak wolnego spotu)")


def zapisz_spot_gracz_depo(stan_dir, t, powod):
    p = Path(stan_dir) / PLIK_SPOT_GRACZ_DEPO
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(PLIK_SPOT_GRACZ_DEPO + ".tmp")
        tmp.write_text(json.dumps({"t": float(t), "powod": powod}, ensure_ascii=False))
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def usun_spot_gracz_depo(stan_dir):
    try:
        (Path(stan_dir) / PLIK_SPOT_GRACZ_DEPO).unlink()
        return True
    except OSError:
        return False
