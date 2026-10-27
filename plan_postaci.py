#!/usr/bin/env python3
"""Plan rozwoju postaci prowadzony przez nadzorcę (23.10, Karol: „Wszystko powinien robić nadzorca, powinien mieć jakiś plan”).

Plik: instancje/_wspolne/plan_postaci.json (opis kształtu: NADZORCA.md, sekcja „Plan postaci”).
  {"postacie": {"<id>": {"spot_przypiety": true, "spot_przypiety_powod": "...",
                         "zostan_w_depo": true, "zostan_w_depo_powod": "...",
                         "zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": "RRRR-MM-DD GG:MM:SS", "wyloguj_w_depo": true,
                         "kroki": [{"id": "...", "warunek": "poziom >= 9", "akcja": "tryb ostrozny,runy", "powod": "...", "zrobione_t": null}]}}}
Warunki:  poziom >= N | po_refillu | przy_nastepnym_starcie
          | po_zwolnieniu <id_postaci> <mapa> +<N>min (23.10, Karol: odchyd wchodzi na spot gebelisha ~10 min po tym, jak ten go zwolni;
            tylko z akcją `mapa` na TĘ SAMĄ mapę; cel ścisły: bez zamienników, zajęty = krok czeka; sygnał „zwolnił” liczy nadzorca, patrz NADZORCA.md)
Akcje:    wroc (do miasta i stoi; tylko z warunkiem poziomu) | tryb <lista> (restart bota na tej samej mapie z nowym trybem)
          | mapa <mapa> [tryb] (spot na następny start; przy warunku poziomu: WROC i start na tym spocie)
`zostan_w_depo` (23.10, Karol): postać po dojściu do depo (STOP) zostaje tam; nadzorca nie wznawia, nie restartuje, nie robi serwisu/relogu/wylogowania.
`zostan_w_depo_po_refillach: N` (24.10, Karol: „2 bp UH-ów, potem depo i wylogowanie”): ta sama flaga, ale uzbrojona dopiero po N refillach liczonych od
`zostan_w_depo_od` (licznik instancje/<id>/refille.json dopisuje refill_auto); wcześniej postać żyje jak bez flagi (refill, powrót na spot). `wyloguj_w_depo`:
przy uzbrojonej fladze nadzorca wylogowuje postać stojącą w depo ze STOP (kod plan-wyloguj-depo) i nie loguje jej ponownie. Reguła: zostan_depo.py.
`domyslne` (25.10, Karol: „ma być jako default, że postacie wracają do depo, robią loga i czekają na mnie”): klucz NAJWYŻSZEGO poziomu planu, obok „postacie”:
{"domyslne": {"wlaczone": true, "zostan_w_depo": true, "wyloguj_w_depo": true}} = te pola dla WSZYSTKICH postaci (też bez wpisu), o ile wpis postaci ich sam nie ustawia
(pole we wpisie, także false, wygrywa). Bez klucza albo bez `wlaczone: true` = domyślne wyłączone. Reguła: zostan_depo.py (`domyslne`, `parsuj`).
`przerwa` (24.10, Karol: „nadzorca ma sam robić przerwy postaci i ewentualnie zmieniać spot”): {"min": 60, "rozrzut_min": 10, "kiedy": "po_refillu" | "teraz",
"zmien_spot": "nie" | "jesli_gracz", "gracz": "Nick", "powod": "..."}; jednorazowa (stan: wylogowano_t, do_t, gracz_wykryty, zrobione_t pisze nadzorca). Reguła i opis
pól: przerwa.py, spec dane_tibia/SPEC_przerwa_postaci_1024.md; ustawia ją `plan_postaci.py przerwa <id> <min> [--teraz]`.
Krok wykonuje się RAZ (`zrobione_t`, zapis atomowy pod flock). Zaplanowana mapa/tryb nie trafia do ostatni_start.<id>.env z wyprzedzeniem:
konsumuje je dopiero start (refill przez uruchom.sh -> `plan_postaci.py start <id> --refill`, albo start/restart nadzorcy), a env zapisuje uruchom.sh.

  python3 -I plan_postaci.py start <id> [--refill] [--bez-procesow]   wypisuje MAPA=… TRYB=… (do eval w uruchom.sh), gdy jest krok do zużycia
  python3 -I plan_postaci.py pokaz [id]                               plan w skrócie (tylko odczyt)
  python3 -I plan_postaci.py przerwa <id> [min] [--teraz] [--rozrzut N] [--zmien-spot nie|jesli_gracz] [--gracz Nick] [--powod T] [--anuluj] [--nadpisz]
                                                                      przerwa postaci: po najbliższym refillu (domyślnie) albo od razu (--teraz)
  python3 -I plan_postaci.py blanki                                   {"blanki": N|null} z plecaka postaci RETRONIC_ID (tylko odczyt)
Tylko stdlib. Zmiana planu przez model nie jest na białej liście nadzorcy: plik edytuje Karol (albo agent z jego polecenia)."""
import argparse
import fcntl
import json
import os
import re
import shlex
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import grafik as G  # noqa: E402
import zostan_depo as ZD  # noqa: E402
import przerwa as PR  # noqa: E402
import spoty as SP  # noqa: E402

FMT = "%Y-%m-%d %H:%M:%S"
UH_BLANK_ID = 3147              # jak uh.UH_BLANK_ID (ID blanku w plecaku); kopia, żeby nie ciągnąć uh.py do haka uruchom.sh
BLANKI_MIN = 1                  # ile blanków w plecaku wystarcza na start trybu `runy` (krok może to zmienić polem `blanki_min`)
OSTRZEZENIE_PRZERWA_H = 6       # „brak wolnego spotu” powiadamia najwyżej raz na tyle godzin na krok
RE_WARUNEK_POZIOM = re.compile(r"^poziom\s*>=\s*(\d+)$")
RE_WARUNEK_ZWOLNIENIE = re.compile(r"^po_zwolnieniu\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s+\+(\d{1,4})\s*min$")
RE_NAZWA = re.compile(r"^[A-Za-z0-9_]+$")
RE_TRYB = re.compile(r"^[A-Za-z0-9_,+]+$")
RE_TRYB_MAPA = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[TRYB\] mapa (\S+?):")
RE_TRYB_TRYB = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[TRYB\] tryb (\S*?):")


# ---------- parsowanie ----------
def parsuj_warunek(txt):
    if not isinstance(txt, str):
        raise ValueError(f"warunek musi być tekstem, jest {txt!r}")
    t = txt.strip()
    if t in ("po_refillu", "przy_nastepnym_starcie"):
        return {"typ": t}
    m = RE_WARUNEK_POZIOM.match(t)
    if m and int(m[1]) > 0:
        return {"typ": "poziom", "n": int(m[1])}
    m = RE_WARUNEK_ZWOLNIENIE.match(t)
    if m:
        return {"typ": "po_zwolnieniu", "kto": m[1], "mapa": m[2], "min": int(m[3])}
    raise ValueError(f"nieznany warunek {txt!r} (dozwolone: poziom >= N | po_refillu | przy_nastepnym_starcie | po_zwolnieniu <id> <mapa> +Nmin)")


def parsuj_akcje(txt):
    if not isinstance(txt, str):
        raise ValueError(f"akcja musi być tekstem, jest {txt!r}")
    c = txt.split()
    if c == ["wroc"]:
        return {"typ": "wroc"}
    if len(c) == 2 and c[0] == "tryb" and RE_TRYB.match(c[1]):
        return {"typ": "tryb", "tryb": c[1]}
    if len(c) in (2, 3) and c[0] == "mapa" and RE_NAZWA.match(c[1]) and (len(c) == 2 or RE_TRYB.match(c[2])):
        return {"typ": "mapa", "mapa": c[1], "tryb": c[2] if len(c) == 3 else None}
    raise ValueError(f"nieznana akcja {txt!r} (dozwolone: wroc | tryb <lista> | mapa <mapa> [tryb])")


def opis_warunku(w):
    if w["typ"] == "po_zwolnieniu":
        return f"po_zwolnieniu {w['kto']} {w['mapa']} +{w['min']}min"
    return f"poziom >= {w['n']}" if w["typ"] == "poziom" else w["typ"]


def opis_akcji(a):
    if a["typ"] == "wroc":
        return "wroc"
    if a["typ"] == "tryb":
        return f"tryb {a['tryb']}"
    return f"mapa {a['mapa']}" + (f" {a['tryb']}" if a.get("tryb") else "")


class Krok:
    def __init__(self, sur, warunek, akcja):
        self.sur = sur
        self.id = sur["id"]
        self.warunek, self.akcja = warunek, akcja
        self.powod = str(sur.get("powod") or "")
        self.zrobione_t = sur.get("zrobione_t") or None
        self.uzbrojone_t = sur.get("uzbrojone_t") or None
        self.uzbrojone_mapa = sur.get("uzbrojone_mapa") or None
        self.tylko_refill = bool(sur.get("tylko_refill"))
        self.ostrzezenie_t = sur.get("ostrzezenie_t") or None
        try:
            self.blanki_min = max(1, int(sur.get("blanki_min", BLANKI_MIN)))
        except (TypeError, ValueError):
            self.blanki_min = BLANKI_MIN

    def opis(self):
        return f"{opis_warunku(self.warunek)} -> {opis_akcji(self.akcja)}"


class PlanPostaci:
    def __init__(self):
        self.kroki = []
        self.spot_przypiety = False
        self.spot_przypiety_powod = ""
        self.zostan_w_depo = False          # 23.10 (Karol): po dojściu do depo postać zostaje w depo (invincible, dawajkesh, wydra)
        self.zostan_w_depo_powod = ""
        self.zostan = ZD.Zostan()           # 24.10: pełny odczyt flagi (po_refillach, od, wyloguj_w_depo); zostan_w_depo = zostan.flaga
        self.zostan_w_depo_po_refillach = 0
        self.zostan_w_depo_od = ""
        self.wyloguj_w_depo = False
        self.przerwa = None                 # 24.10: przerwa.Przerwa (jednorazowa przerwa postaci, robi ją nadzorca) albo None


class Plan:
    def __init__(self):
        self.postacie = {}
        self.bledy = []
        self.domyslne = None        # 25.10: klucz „domyslne” planu (zostan_depo.domyslne) albo None = wyłączone
        self.zostan_domyslny = ZD.Zostan()      # flaga „zostań w depo” postaci BEZ wpisu w „postacie” (tylko domyślne; wyłączone = flaga False)
        self.nieczytelny = False    # cały plik nieczytelny: spot_przypiety nieznany, więc nadzorca nie zmienia żadnych spotów


def sciezka(korzen):
    return G.wspolne(korzen) / "plan_postaci.json"


def _surowy(korzen):
    """(dane, błąd). Brak pliku = pusty plan, bez błędu."""
    p = sciezka(korzen)
    try:
        tekst = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"postacie": {}}, None
    except OSError as e:
        return None, f"plan_postaci.json nieczytelny: {e!r}"
    try:
        d = json.loads(tekst)
        if not isinstance(d, dict) or not isinstance(d.get("postacie", {}), dict):
            raise ValueError("oczekiwano obiektu z kluczem „postacie”")
    except ValueError as e:
        return None, f"plan_postaci.json nieczytelny (JSON): {e}"
    d.setdefault("postacie", {})
    return d, None


def wczytaj(korzen):
    """Plan z pliku. Błędny krok trafia do `bledy` i nie psuje reszty; nieczytelny plik = pusty plan + błąd."""
    plan = Plan()
    d, blad = _surowy(korzen)
    if blad:
        plan.bledy.append(blad)
        plan.nieczytelny = True
        return plan
    plan.domyslne, blad_dom = ZD.domyslne(d)          # 25.10 (Karol): domyślnie każda postać w depo zostaje i jest wylogowana (włącznik: domyslne.wlaczone)
    if blad_dom:
        plan.bledy.append(blad_dom)
    plan.zostan_domyslny = ZD.parsuj(None, plan.domyslne)
    for id_, pc in d["postacie"].items():
        if str(id_).startswith("_"):
            continue
        if not isinstance(pc, dict):
            plan.bledy.append(f"postać {id_}: wpis nie jest obiektem")
            continue
        wynik = PlanPostaci()
        wynik.spot_przypiety = bool(pc.get("spot_przypiety"))
        wynik.spot_przypiety_powod = str(pc.get("spot_przypiety_powod") or "")
        z = ZD.parsuj(pc, plan.domyslne)
        if z.blad:
            plan.bledy.append(f"postać {id_}: {z.blad}")
        wynik.zostan = z
        wynik.zostan_w_depo = z.flaga
        wynik.zostan_w_depo_powod = z.powod
        wynik.zostan_w_depo_po_refillach = z.po_refillach
        wynik.zostan_w_depo_od = z.od
        wynik.wyloguj_w_depo = z.wyloguj
        if pc.get("przerwa") is not None:
            try:
                wynik.przerwa = PR.parsuj(pc["przerwa"])
            except ValueError as e:
                plan.bledy.append(f"postać {id_}: {e}")
        widziane = set()
        kroki = pc.get("kroki") or []
        if not isinstance(kroki, list):
            plan.bledy.append(f"postać {id_}: „kroki” nie jest listą")
            kroki = []
        for i, k in enumerate(kroki):
            nazwa = f"postać {id_}, krok #{i + 1}"
            try:
                if not isinstance(k, dict) or not isinstance(k.get("id"), str) or not k["id"].strip():
                    raise ValueError("brak tekstowego pola „id”")
                nazwa = f"postać {id_}, krok {k['id']}"
                if k["id"] in widziane:
                    raise ValueError("zdublowane id (zostaje pierwszy)")
                w, a = parsuj_warunek(k.get("warunek")), parsuj_akcje(k.get("akcja"))
                if a["typ"] == "wroc" and w["typ"] != "poziom":
                    raise ValueError("akcja wroc ma sens tylko z warunkiem poziomu (po refillu/starcie bot dopiero rusza)")
                if w["typ"] == "po_zwolnieniu":
                    if a["typ"] != "mapa" or a["mapa"] != w["mapa"]:
                        raise ValueError("warunek po_zwolnieniu ma sens tylko z akcją `mapa` na tę samą mapę, którą zwalnia tamta postać")
                    if w["kto"] == id_:
                        raise ValueError("po_zwolnieniu: postać nie może czekać na samą siebie")
                widziane.add(k["id"])
                wynik.kroki.append(Krok(k, w, a))
            except ValueError as e:
                plan.bledy.append(f"{nazwa}: {e}")
        plan.postacie[id_] = wynik
    return plan


# ---------- zapis (atomowy, pod flock) ----------
@contextmanager
def _blokada(korzen):
    W = G.wspolne(korzen)
    W.mkdir(parents=True, exist_ok=True)
    f = open(W / "plan_postaci.lock", "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


def _zmien(korzen, id_, krok_id, fn):
    """Pod blokadą: odczyt surowego pliku, fn(krok_surowy) -> bool (zmieniono), zapis atomowy (tmp + replace). -> bool."""
    with _blokada(korzen):
        d, blad = _surowy(korzen)
        if blad:
            return False
        pc = d["postacie"].get(id_)
        if not isinstance(pc, dict):
            return False
        for k in pc.get("kroki") or []:
            if isinstance(k, dict) and k.get("id") == krok_id:
                if not fn(k):
                    return False
                p = sciezka(korzen)
                tmp = p.with_name(p.name + ".tmp")
                tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                tmp.replace(p)
                return True
    return False


def _zmien_pc(korzen, id_, fn, utworz=False):
    """Pod blokadą: fn(wpis_postaci_surowy) -> bool (zmieniono); zapis atomowy (tmp + replace). `utworz`: brakujący wpis postaci powstaje pusty. -> bool."""
    with _blokada(korzen):
        d, blad = _surowy(korzen)
        if blad:
            return False
        pc = d["postacie"].get(id_)
        if not isinstance(pc, dict):
            if not utworz or pc is not None:
                return False
            pc = d["postacie"][id_] = {}
        if not fn(pc):
            return False
        p = sciezka(korzen)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(p)
        return True


def przerwa_ustaw(korzen, id_, wpis, nadpisz=False):
    """Uzbraja przerwę (CLI `przerwa`). False = już jest niezakończona przerwa (chyba że `nadpisz`) albo plan nieczytelny."""
    def f(pc):
        stara = pc.get("przerwa")
        if isinstance(stara, dict) and not stara.get("zrobione_t") and not nadpisz:
            return False
        pc["przerwa"] = wpis
        return True
    return _zmien_pc(korzen, id_, f, utworz=True)


def przerwa_zapisz(korzen, id_, pola, warunek=None):
    """Dopisuje pola stanu do `przerwa` (wylogowano_t, do_t, gracz_wykryty, zrobione_t); `warunek(przerwa_surowa)` -> bool chroni przed wyścigiem
    (np. „jeszcze nie zrobiona”). Wartość None w `pola` usuwa klucz. -> bool."""
    def f(pc):
        w = pc.get("przerwa")
        if not isinstance(w, dict) or (warunek is not None and not warunek(w)):
            return False
        for k, v in pola.items():
            if v is None:
                w.pop(k, None)
            else:
                w[k] = v
        return True
    return _zmien_pc(korzen, id_, f)


def przerwa_usun(korzen, id_):
    """Usuwa wpis `przerwa` (CLI `przerwa --anuluj`; nie dotyka przerwy już trwającej — tę kończy nadzorca powrotem). -> bool."""
    def f(pc):
        w = pc.get("przerwa")
        if not isinstance(w, dict) or w.get("wylogowano_t") and not w.get("zrobione_t"):
            return False
        del pc["przerwa"]
        return True
    return _zmien_pc(korzen, id_, f)


def oznacz_zrobione(korzen, id_, krok_id, teraz, powod=""):
    """Zapisuje `zrobione_t`, o ile krok nie był już zrobiony (False = ktoś już go zużył albo kroku nie ma)."""
    def f(k):
        if k.get("zrobione_t"):
            return False
        k["zrobione_t"] = teraz.strftime(FMT)
        if powod:
            k["zrobione_powod"] = str(powod)[:200]
        return True
    return _zmien(korzen, id_, krok_id, f)


def uzbroj(korzen, id_, krok_id, teraz, mapa=None, tylko_refill=False):
    """Krok z warunkiem poziomu, którego efekt wymaga następnego startu (WROC zlecony): czeka na start jako „uzbrojony”."""
    def f(k):
        if k.get("zrobione_t") or k.get("uzbrojone_t"):
            return False
        k["uzbrojone_t"] = teraz.strftime(FMT)
        if mapa:
            k["uzbrojone_mapa"] = mapa
        if tylko_refill:
            k["tylko_refill"] = True
        return True
    return _zmien(korzen, id_, krok_id, f)


def ostrzez_raz(korzen, id_, krok_id, teraz, zapis=True):
    """True, gdy wolno powiadomić o niewykonanym kroku (nie częściej niż co OSTRZEZENIE_PRZERWA_H); zapisuje `ostrzezenie_t`."""
    wynik = []

    def f(k):
        t = k.get("ostrzezenie_t")
        try:
            wiek = (teraz - datetime.strptime(t, FMT)) if t else None
        except ValueError:
            wiek = None
        if wiek is not None and wiek < timedelta(hours=OSTRZEZENIE_PRZERWA_H):
            return False
        wynik.append(True)
        if not zapis:
            return False
        k["ostrzezenie_t"] = teraz.strftime(FMT)
        return True
    ok = _zmien(korzen, id_, krok_id, f)
    return bool(ok or (not zapis and wynik))


# ---------- bramki (dla haka uruchom.sh; nadzorca ma własne) ----------
def _tryb_nadzoru_zywy(korzen):
    W = G.wspolne(korzen)
    return (W / "NADZOR_ZYWO").exists() or (W / "NADZOR_NAPRAWY").exists() or os.environ.get("NADZOR_NAPRAWY") == "1"


def bramki(korzen, id_, teraz):
    """Powód, dla którego plan nie może zmienić startu postaci, albo None. Te same wyłączniki co nadzorca (pauza, nadzor:false, STOP_RECZNY,
    wstrzymanie, cisza) plus: bez NADZOR_NAPRAWY / NADZOR_ZYWO nadzorca pracuje w cieniu i niczego nie zmienia."""
    W = G.wspolne(korzen)
    if (W / "NADZOR_PAUZA").exists():
        return "NADZOR_PAUZA: zero akcji"
    try:
        profil = json.loads((Path(korzen) / "instancje" / id_ / "profil.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        profil = {}
    poza = G.poza_nadzorem(profil, G.wczytaj_konfig(korzen).get("postacie", {}).get(id_), teraz)
    if poza:
        return poza
    if (Path(korzen) / "instancje" / id_ / "STOP_RECZNY").exists():
        return "STOP_RECZNY: Karol gra, zero akcji dla tej postaci"
    try:
        h = (json.loads((W / "nadzor_stan.json").read_text(encoding="utf-8")).get("postacie", {}).get(id_) or {}).get("hold")
    except (OSError, ValueError, AttributeError):
        h = None
    if h:
        return f"wstrzymana po eskalacji ({h.get('powod')})"
    if os.environ.get("RETRONIC_POWIADOMIENIA", "").strip() == "0":
        return "cisza (RETRONIC_POWIADOMIENIA=0): kroki planu bez powiadomienia nie idą"
    if (Path(korzen) / "cisza").exists():
        return "cisza (plik cisza): kroki planu bez powiadomienia nie idą"
    if not _tryb_nadzoru_zywy(korzen):
        return "nadzorca pracuje w cieniu (brak NADZOR_NAPRAWY / NADZOR_ZYWO): plan nie zmienia startów"
    return None


_bramki = bramki


# ---------- mapy: bieżąca, zajęte, cel ----------
def biezaca(korzen, id_, teraz=None):
    """(mapa, tryb) z tryb.log tej instancji (z korektą `Mózg: … trasa`, jeśli da się wczytać nadzor.py)."""
    try:
        import nadzor  # noqa: PLC0415
        m, t, _ = nadzor.mapa_tryb_biezace(korzen, id_, teraz)
        return m, t
    except Exception:       # noqa: BLE001
        pass
    mapa = tryb = None
    try:
        tekst = (Path(korzen) / "instancje" / id_ / "logi" / "tryb.log").read_text(encoding="utf-8", errors="replace")[-300_000:]
    except OSError:
        return None, None
    for l in tekst.splitlines():
        m = RE_TRYB_MAPA.match(l)
        if m:
            mapa, tryb = m[1], None
            continue
        m = RE_TRYB_TRYB.match(l)
        if m and mapa is not None:
            tryb = ",".join(x for x in m[1].split("+") if x)
    return mapa, tryb


def _procesy_bota(id_):
    import instancja  # noqa: PLC0415
    return instancja.procesy(r"(mozg|cavebot)\.py", id_=id_)


def zajete_mapy(korzen, id_, procesy_bota=None):
    """Bieżące mapy INNYCH naszych botów (instancje z działającym procesem bota; mapa z tryb.log, nie z env)."""
    procesy_bota = procesy_bota or _procesy_bota
    zaj = set()
    kat = Path(korzen) / "instancje"
    try:
        wpisy = sorted(p.name for p in kat.iterdir() if p.is_dir() and not p.name.startswith("_") and (p / "profil.json").exists())
    except OSError:
        return zaj
    for inny in wpisy:
        if inny == id_:
            continue
        try:
            if not procesy_bota(inny):
                continue
        except Exception:       # noqa: BLE001
            continue
        mapa = biezaca(korzen, inny)[0]
        if mapa:
            zaj.add(mapa)
    return zaj


def _tabela(korzen, tabela=None):
    if tabela is not None:
        return tabela
    try:
        t = SP.wczytaj(korzen)
    except Exception:       # noqa: BLE001
        return None
    return None if t.blad else t


def wybierz_cel(korzen, id_, cel, zajete, poziom=None, tabela=None, ekwipunek=None, scisle=False):
    """(mapa, komunikat). Cel wolny -> (cel, None). Zajęty (inny nasz bot na tej jaskini) -> inny wolny spot z tego samego miasta i identycznych
    widełek poziomu (tylko `auto`, bez znanego braku liny/łopaty). Brak -> (None, powód). Poziom poza widełkami celu -> (None, powód).
    scisle=True (krok `po_zwolnieniu`): cel zajęty = (None, powód), nigdy zamiennik (cały sens kroku to wejście na TEN spot)."""
    tab = _tabela(korzen, tabela)
    zajete = set(zajete or ())
    jask = (lambda m: tab.jaskinia_mapy(m)) if tab is not None else (lambda m: m)       # noqa: E731
    spot = tab.spoty.get(cel) if tab is not None else None
    if tab is not None and spot is None:
        return None, f"mapa {cel} nie ma wpisu w tabeli spotów (dane_tibia/spoty_nadzorca.json): krok niewykonany"
    if spot is not None and poziom is not None and spot.poziom and not (spot.poziom[0] <= poziom <= spot.poziom[1]):
        return None, f"poziom {poziom} poza widełkami {spot.poziom[0]}-{spot.poziom[1]} celu {cel}: krok niewykonany"
    zaj_j = {jask(m) for m in zajete}
    if jask(cel) not in zaj_j:
        return cel, None
    if scisle:
        return None, f"cel {cel} zajęty (jaskinia {jask(cel)} ma tam innego bota); krok ścisły, bez zamiennika: czeka"
    if spot is None:
        return None, f"brak wolnego spotu: cel {cel} zajęty przez inny bot, a tabela spotów nie daje alternatyw"
    eq = None
    alts = []
    for nazwa in sorted(tab.spoty):
        s = tab.spoty[nazwa]
        if nazwa == cel or s.baza or s.miasto != spot.miasto or tuple(s.poziom) != tuple(spot.poziom) or not s.auto or s.jaskinia in zaj_j:   # 26.10: wariant-łącznik (s.baza) to nie zamiennik
            continue
        if s.wymaga:
            if eq is None:
                eq = (ekwipunek() if callable(ekwipunek) else ekwipunek) or {}
            if any(eq.get(w) is False for w in s.wymaga):
                continue
        if all(tab.spoty[a].jaskinia != s.jaskinia for a in alts):
            alts.append(nazwa)
    if alts:
        return alts[0], f"cel {cel} zajęty (jaskinia {spot.jaskinia} ma tam innego bota): biorę {alts[0]} (to samo miasto i widełki {spot.poziom[0]}-{spot.poziom[1]})"
    lo, hi = spot.poziom
    return None, (f"brak wolnego spotu w widełkach {lo}-{hi} ({spot.miasto}): cel {cel} zajęty przez innego bota, "
                  f"zajęte jaskinie: {', '.join(sorted(zaj_j)) or '-'}; krok niewykonany")


# ---------- blanki ----------
def blanki_z_odczytu(odp):
    """Liczba blanków w otwartych kontenerach z odpowiedzi strażnika (`kontenery`) albo None (brak odczytu, nic nie otwarte)."""
    if not isinstance(odp, dict) or odp.get("blad"):
        return None
    kont = odp.get("kontenery")
    if not isinstance(kont, list) or not kont:
        return None
    n = 0
    for k in kont:
        for p in (k or {}).get("przedmioty", []) or []:
            try:
                if int(p.get("id", -1)) == UH_BLANK_ID:
                    n += max(1, int(p.get("ilosc", 1) or 1))
            except (TypeError, ValueError):
                continue
    return n


def blanki_postaci(zapytaj=None):
    try:
        if zapytaj is None:
            import loot  # noqa: PLC0415
            zapytaj = loot._zapytaj
        return blanki_z_odczytu(zapytaj({"cmd": "kontenery"}))   # 24.10: z "ekwipunek": True strażnik zwraca sam ekwipunek (kontenery.obsluz), blanki były zawsze None
    except Exception:       # noqa: BLE001
        return None


# ---------- zużycie kroków przy starcie ----------
def _pasuje(k, rodzaj):
    t = k.warunek["typ"]
    if t == "po_refillu":
        return rodzaj == "refill"
    if t == "przy_nastepnym_starcie":
        return rodzaj in ("refill", "nadzor")
    if t in ("poziom", "po_zwolnieniu"):
        return bool(k.uzbrojone_t) and (rodzaj == "refill" or not k.tylko_refill)
    return False


def _dziennik(korzen, teraz, id_, akcja, wynik, powod, tryb="zywo"):
    try:
        kat = G.wspolne(korzen) / "logi"
        kat.mkdir(parents=True, exist_ok=True)
        rek = {"t": teraz.strftime(FMT), "tryb": tryb, "id": id_, "akcja": akcja, "wynik": wynik, "powod": powod}
        with open(kat / f"nadzor-{teraz:%Y%m%d}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rek, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _powiadom_info(id_, tytul, tresc):
    """Zwykłe powiadomienie (jak WykonawcaZywy.powiadom_info): klucz „stop-…” przechodzi filtr powiadom.py. Bez wyjątków."""
    try:
        import powiadom  # noqa: PLC0415
        return bool(powiadom.powiadom(tytul, tresc, "normal", klucz=f"stop-nadzor-{id_}-{tytul}"))
    except Exception:       # noqa: BLE001
        return False


def konsumuj_start(korzen, id_, rodzaj, teraz, zapis=True, zajete=None, poziom=None, ekwipunek=None, powiadom=None, log=None,
                   bramki=True, biezaca=None, tabela=None, ostrzez=None, zajete_bez=None):
    """Kroki planu, które ten start ma zużyć. rodzaj: „refill” (STARTUJ=1 z refill.sh/serwis.sh) albo „nadzor” (login, relog, restart, wznów).
    -> {"mapa", "tryb", "kroki": [id]} albo None. zapis=False: tylko wynik (cień, podgląd), bez zapisu, powiadomień i dziennika zapisów.
    Mapa zajęta przez innego bota -> inny wolny spot z tych samych widełek; brak -> krok czeka (dziennik + powiadomienie raz na 6 h).
    ostrzez: czy wolno powiadomić o braku wolnego spotu (domyślnie = zapis; nadzorca w trybie na żywo daje True przy zapis=False).
    zajete_bez(kto): zajęte mapy BEZ spotu zapisanego dla postaci `kto` (krok `po_zwolnieniu`: postać, która spot zwolniła, ma go jeszcze w stanie nadzorcy,
    ale bot na nim nie działa; liczy się tylko jej działający bot). Bez tego parametru krok używa `zajete`."""
    log = log or (lambda *a, **k: None)
    powiadom = powiadom or (lambda *a, **k: None)
    plan = wczytaj(korzen)
    if plan.bledy:
        log("plan", "blad", "plan_postaci.json: " + "; ".join(plan.bledy))
    pc = plan.postacie.get(id_)
    if pc is None:
        return None
    kand = [k for k in pc.kroki if not k.zrobione_t and _pasuje(k, rodzaj)]
    if not kand:
        return None
    if bramki:
        odm = _bramki(korzen, id_, teraz)
        if odm:
            log("plan", "pominięty", f"kroki planu ({', '.join(k.id for k in kand)}) czekają: {odm}")
            return None
    mapa, tryb = biezaca if biezaca is not None else globals()["biezaca"](korzen, id_, teraz)
    if zajete is None:
        zajete = zajete_mapy(korzen, id_)
    wzięte = []
    for k in kand:
        a = k.akcja
        if a["typ"] == "mapa":
            scisle = k.warunek["typ"] == "po_zwolnieniu"
            zaj_k = zajete_bez(k.warunek["kto"]) if (scisle and zajete_bez) else zajete
            cel, kom = wybierz_cel(korzen, id_, a["mapa"], zaj_k, poziom, tabela, ekwipunek, scisle=scisle)
            if cel is None:
                log("plan", "pominięty", f"krok {k.id}: {kom}")
                if (zapis if ostrzez is None else ostrzez) and ostrzez_raz(korzen, id_, k.id, teraz):
                    powiadom(id_, f"{id_}: plan czeka, brak wolnego spotu"[:80], f"Krok {k.id} ({k.opis()}) niewykonany: {kom}")
                continue
            if kom:
                log("plan", "zmiana celu", f"krok {k.id}: {kom}")
            mapa = cel
            tryb = a["tryb"] or tryb
        elif a["typ"] == "tryb":
            m = k.uzbrojone_mapa or mapa
            if not m:
                log("plan", "pominięty", f"krok {k.id}: nieznana bieżąca mapa (brak [TRYB] mapa w tryb.log), nie zgaduję")
                continue
            mapa, tryb = m, a["tryb"]
        else:
            continue
        wzięte.append(k)
    if not wzięte:
        return None
    if zapis:
        zuzyte = []
        for k in wzięte:
            if oznacz_zrobione(korzen, id_, k.id, teraz, f"start ({rodzaj}): {mapa} / {tryb or '-'}"):
                zuzyte.append(k)
                if not k.uzbrojone_t:       # uzbrojony krok powiadomił już przy zleceniu WROC
                    powiadom(id_, f"{id_}: plan — {opis_akcji(k.akcja)}"[:80],
                             f"Krok {k.id}: {k.opis()} ({k.powod}). Start: {mapa} / {tryb or '-'}.")
        if not zuzyte:
            return None
        wzięte = zuzyte
    return {"mapa": mapa, "tryb": tryb, "kroki": [k.id for k in wzięte]}


# ---------- opis planu (stan, pokaz) ----------
def stan_kroku(k, poziom=None, teraz=None):
    teraz = teraz or datetime.now()
    if k.zrobione_t:
        try:
            d = datetime.strptime(k.zrobione_t, FMT)
            return "zrobione " + (d.strftime("%H:%M") if d.date() == teraz.date() else d.strftime("%m-%d %H:%M"))
        except ValueError:
            return "zrobione " + k.zrobione_t
    if k.uzbrojone_t:
        return "uzbrojony: czeka na " + ("następny refill" if k.tylko_refill else "następny start") + f" (od {k.uzbrojone_t[11:16]})"
    w = k.warunek
    if w["typ"] == "poziom":
        if poziom is not None and poziom >= w["n"]:
            return f"warunek spełniony (poziom {poziom}): wykona się w najbliższym przebiegu, poza walką"
        return f"czeka na poziom {w['n']} (teraz {poziom if poziom is not None else '?'})"
    if w["typ"] == "po_zwolnieniu":
        return f"czeka, aż {w['kto']} zwolni {w['mapa']} (+{w['min']} min)"
    return "czeka na najbliższy refill" if w["typ"] == "po_refillu" else "czeka na najbliższy start bota (refill, login, restart)"


def opis_planu(korzen, id_, poziom=None, teraz=None, plan=None):
    plan = plan or wczytaj(korzen)
    pc = plan.postacie.get(id_)
    if pc is None:
        zd = plan.zostan_domyslny       # 25.10: postać bez wpisu dostaje tylko pola domyślne (gdy włączone)
        return {"kroki": [], "nastepny": None, "spot_przypiety": False, "spot_przypiety_powod": "",
                "zostan_w_depo": zd.flaga, "zostan_w_depo_powod": zd.powod, "zostan_w_depo_po_refillach": 0, "zostan_w_depo_od": "",
                "wyloguj_w_depo": zd.wyloguj, "przerwa": "", "zostan_domyslne": zd.z_domyslnych}
    kroki = [{"id": k.id, "warunek": opis_warunku(k.warunek), "akcja": opis_akcji(k.akcja), "powod": k.powod,
              "stan": stan_kroku(k, poziom, teraz), "zrobione_t": k.zrobione_t} for k in pc.kroki]
    nast = next((x for x, k in zip(kroki, pc.kroki) if not k.zrobione_t), None)
    return {"kroki": kroki, "nastepny": nast, "spot_przypiety": pc.spot_przypiety, "spot_przypiety_powod": pc.spot_przypiety_powod,
            "zostan_w_depo": pc.zostan_w_depo, "zostan_w_depo_powod": pc.zostan_w_depo_powod,
            "zostan_w_depo_po_refillach": pc.zostan_w_depo_po_refillach, "zostan_w_depo_od": pc.zostan_w_depo_od, "wyloguj_w_depo": pc.wyloguj_w_depo,
            "przerwa": PR.opis(pc.przerwa) if pc.przerwa else "", "zostan_domyslne": pc.zostan.z_domyslnych}


# ---------- CLI ----------
def _korzen():
    return Path(os.environ.get("RETRONIC_NADZOR_KORZEN") or DIR)


def _poziom_znany(korzen, id_, teraz):
    try:
        z = json.loads((G.wspolne(korzen) / "nadzor_stan.json").read_text(encoding="utf-8"))["postacie"][id_]["poziom"]
        if isinstance(z.get("wartosc"), int) and (teraz - datetime.strptime(z["t"], G.FMT)) < timedelta(hours=24):
            return z["wartosc"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _cmd_przerwa(a, korzen, teraz):
    if not RE_NAZWA.match(a.id) or not (Path(korzen) / "instancje" / a.id).is_dir():
        print(f"przerwa: nieznana instancja {a.id!r}", file=sys.stderr)
        return 2
    if a.anuluj:
        ok = przerwa_usun(korzen, a.id)
        print(f"{a.id}: przerwa usunięta" if ok else f"{a.id}: brak przerwy do usunięcia (albo już trwa — kończy ją nadzorca powrotem)")
        return 0 if ok else 1
    if a.min is None:
        print("przerwa: podaj długość w minutach (np. `przerwa gebelish 60`)", file=sys.stderr)
        return 2
    wpis = {"min": a.min, "rozrzut_min": a.rozrzut, "kiedy": "teraz" if a.teraz else "po_refillu", "zmien_spot": a.zmien_spot,
            "powod": a.powod, "ustawiono_t": teraz.strftime(FMT)}
    if a.gracz:
        wpis["gracz"] = a.gracz
    try:
        PR.parsuj(wpis)
    except ValueError as e:
        print(f"przerwa: {e}", file=sys.stderr)
        return 2
    if not przerwa_ustaw(korzen, a.id, wpis, nadpisz=a.nadpisz):
        print(f"{a.id}: już jest niezakończona przerwa (--nadpisz zastępuje, --anuluj usuwa) albo plan nieczytelny", file=sys.stderr)
        return 1
    pr = PR.parsuj(wpis)
    print(f"{a.id}: {PR.opis(pr)}" + ("" if PR.wlaczone(korzen=korzen) else "  (UWAGA: przerwy wyłączone — NADZOR_PRZERWY=0 / nadzor_konfig.json „przerwy”: false)"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="plan_postaci.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("id")
    s.add_argument("--refill", action="store_true")
    s.add_argument("--bez-procesow", action="store_true", help="nie sprawdzaj procesów innych botów (testy)")
    p = sub.add_parser("pokaz")
    p.add_argument("id", nargs="?")
    sub.add_parser("blanki")
    b = sub.add_parser("przerwa", help="uzbraja jednorazową przerwę postaci (robi ją nadzorca); spec dane_tibia/SPEC_przerwa_postaci_1024.md")
    b.add_argument("id")
    b.add_argument("min", nargs="?", type=int, help="długość przerwy w minutach (wylogowana)")
    b.add_argument("--teraz", action="store_true", help="nie czekaj na refill: postać wraca do miasta (WROC) i dopiero tam się wylogowuje")
    b.add_argument("--rozrzut", type=int, default=PR.ROZRZUT_DOMYSLNY, help="± losowy rozrzut powrotu w minutach (domyślnie %(default)s)")
    b.add_argument("--powod", default="")
    b.add_argument("--zmien-spot", choices=PR.ZMIEN_SPOT, default="jesli_gracz", help="po powrocie: zmień spot, gdy przeszkadzał gracz (domyślnie %(default)s)")
    b.add_argument("--gracz", default="", help="nick gracza, który przeszkadzał (powód przerwy); bez niego nadzorca szuka go w logu bota")
    b.add_argument("--anuluj", action="store_true", help="usuń niezakończoną przerwę (nie dotyka przerwy już trwającej)")
    b.add_argument("--nadpisz", action="store_true", help="zastąp istniejącą niezakończoną przerwę")
    a = ap.parse_args(argv)
    korzen = _korzen()
    teraz = datetime.now().replace(microsecond=0)
    if a.cmd == "blanki":
        print(json.dumps({"blanki": blanki_postaci()}))
        return 0
    if a.cmd == "przerwa":
        return _cmd_przerwa(a, korzen, teraz)
    if a.cmd == "pokaz":
        plan = wczytaj(korzen)
        for b in plan.bledy:
            print("BŁĄD PLANU:", b)
        if plan.domyslne is not None:       # 25.10: domyślne WŁĄCZONE (wyłączone = bez linii, wyjście jak przed 25.10)
            print("domyślne: WŁĄCZONE (każda postać bez własnej flagi: zostaje w depo"
                  + (", wylogowana" if plan.domyslne["wyloguj_w_depo"] else "") + (")" if plan.domyslne["zostan_w_depo"] else "; zostan_w_depo=false)"))
        for id_ in ([a.id] if a.id else sorted(plan.postacie)):
            o = opis_planu(korzen, id_, _poziom_znany(korzen, id_, teraz), teraz, plan)
            print(f"{id_}:" + (" [spot przypięty" + (f": {o['spot_przypiety_powod']}" if o["spot_przypiety_powod"] else "") + "]" if o["spot_przypiety"] else "")
                  + (" [zostaje w depo" + (f" po {o['zostan_w_depo_po_refillach']}. refillu od {o['zostan_w_depo_od'] or 'początku'}" if o["zostan_w_depo_po_refillach"] else "")
                     + (" + wylogowanie" if o["wyloguj_w_depo"] else "") + (f": {o['zostan_w_depo_powod']}" if o["zostan_w_depo_powod"] else "") + (" (domyślnie)" if o.get("zostan_domyslne") else "") + "]" if o["zostan_w_depo"] else "")
                  + (f" [{o['przerwa']}]" if o["przerwa"] else ""))
            for k in o["kroki"]:
                print(f"  {k['id']}: {k['warunek']} -> {k['akcja']}  [{k['stan']}]")
            if not o["kroki"]:
                print("  (brak kroków)")
        return 0
    try:
        zajete = set() if a.bez_procesow else None
        r = konsumuj_start(korzen, a.id, "refill" if a.refill else "nadzor", teraz, zajete=zajete,
                           poziom=_poziom_znany(korzen, a.id, teraz),
                           powiadom=_powiadom_info,
                           log=lambda ak, w, po, **e: _dziennik(korzen, teraz, a.id, ak, w, po))
    except Exception as e:      # noqa: BLE001  (hak uruchom.sh jest fail-safe: błąd planu nigdy nie blokuje startu)
        print(f"plan_postaci: {e!r}", file=sys.stderr)
        return 0
    if r:
        print(f"MAPA={shlex.quote(r['mapa'] or '')}")
        print(f"TRYB={shlex.quote(r['tryb'] or '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
