"""Ratunek F2a (SPEC_ratunek_haiku_1019): Haiku w CIENIU. Przy zgłoszonym sygnale (S1-S7) osobny wątek-demon buduje kontekst,
woła `claude -p --model haiku` (klasa Claude z mozg.py, bez narzędzi, limit czasu), waliduje odpowiedź do zamkniętej listy ruchów
i dopisuje rekord `haiku_cien` do logi/ratunek-<data>.jsonl. NIC NIE WYKONUJE i niczego nie zatrzymuje: pętla bota nie czeka
na wątek, nie dzieli z nim żadnej blokady (jedyny zamek jest tutaj i trzymany jest ułamki ms), błąd wątku nie wychodzi na zewnątrz.

Włączenie: RATUNEK_HAIKU=1 i RATUNEK_HAIKU_PYTAJ=1 (domyślnie 0). Limity: jedno wywołanie naraz (sygnał w trakcie pytania =
rekord z `pominiety`), do RATUNEK_LIMIT_H wywołań na godzinę na proces (wywołania Haiku liczą się do limitu 20/h).

Format rekordu (jedna linia jsonl, obok linii sygnałów z ratunek.zglos; linie sygnałów zyskały pole `id`):
  {"rekord": "haiku_cien", "id": <id sygnału>, "kod": "S2", "poz": [x,y,z], "czas": "RRRR-MM-DD GG:MM:SS",
   "haiku_cien": {"ruch": "krok N" | "uzyj_pola 0,-1" | "lina dx,dy" | "idz_do x,y" | "czekaj s" | "czlowiek" | null,
                  "powod": null | "<dlaczego czlowiek>", "dlaczego": "<uzasadnienie modelu, do 300 zn.>",
                  "odpowiedz": "<surowa odpowiedź, do 2000 zn.>", "czas_wywolania_s": 1.8, "czas_zrzutu_s": 0.4, "blad": null | "<tekst>",
                  "zrzut": "ratunek-zrzuty/<id>.jpg" | null, "blad_zrzutu": null | "<tekst>",
                  "pominiety": null | "trwa_pytanie" | "limit_h" | "blad_kontekstu",
                  "wykonano": false, "model": "haiku", "prompt": "<ucięty do 3000 zn.>"}}
`ruch` jest już po walidacji; null tylko przy `pominiety`.
"""
import atexit
import collections
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
HAIKU_TIMEOUT_S = 45.0            # limit czasu jednego wywołania (Claude.timeout); w wątku, więc nie wstrzymuje bota
ODP_MAX = 2000                    # surowa odpowiedź w rekordzie
PROMPT_MAX = 3000
DLACZEGO_MAX = 300
ZRZUTY_MAX = 200                  # ostatnie zrzuty w logi/ratunek-zrzuty/
KATALOG_ZRZUTOW = "ratunek-zrzuty"
WIDOK_X, WIDOK_Y = 7, 5           # widok mapy: |dx|<=7, |dy|<=5 (cavebot.ZASIEG_X/Y)
PROMIEN_PRZEJSC = 10
WYJSCIE_CZEKAJ_S = 1.0            # max czekania przy wyjściu procesu PO zabiciu claude (zatrzymaj.sh czeka 3 s na PID; przegląd 19.10)
CZEKAJ_MAX_S = 10.0
KIERUNKI = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0), "NE": (1, -1), "NW": (-1, -1), "SE": (1, 1), "SW": (-1, 1)}
BEZ_DROGI = 2                     # flaga mapy: schody/dziura (mapa.BEZ_DROGI)
TESTY = bool(os.environ.get("RETRONIC_TESTY"))   # w testach nigdy nie sięgamy po prawdziwego claude (tylko wstrzyknięta atrapa)

SYSTEM = (
    "Jesteś pomocnikiem bota do gry Tibia (widok z góry). Oś x rośnie na wschód (E), oś y na południe (S); "
    "dx,dy to przesunięcie względem postaci (środek widoku). Bot właśnie zachowuje się jak bot (stoi, kręci się, zgubił "
    "trasę lub piętro, kroki bez skutku). Na zrzucie widać ekran gry, w kontekście: pozycję, sygnał, cel, punkty trasy, "
    "znane przejścia pięter, ostatnie ruchy, HP/manę i stwory. Wybierz JEDEN ruch z zamkniętej listy:\n"
    "  krok <N|S|E|W|NE|NW|SE|SW>   jeden krok w stronę\n"
    "  uzyj_pola <dx,dy>            Ctrl+klik w pole (drabina, schody, otwór), |dx|<=7, |dy|<=5\n"
    "  lina <dx,dy>                 użyj liny na polu (otwór w górę), |dx|<=7, |dy|<=5\n"
    "  idz_do <x,y>                 idź do pola w widoku (bezwzględne x,y, to samo piętro)\n"
    "  czekaj <s>                   poczekaj, s <= 10\n"
    "  czlowiek                     nie wiesz albo to wymaga człowieka\n"
    "Nie wymyślaj innych ruchów. Odpowiedz WYŁĄCZNIE jednym obiektem JSON: "
    '{"ruch": "<ruch z listy>", "dlaczego": "<jedno zdanie>"}. W razie wątpliwości: {"ruch": "czlowiek", "dlaczego": "..."}.')


# --- walidacja odpowiedzi (pkt 3 Zachowania) ---
def wyciagnij_obiekt(tekst):
    """Pierwszy obiekt JSON z odpowiedzi (także w bloku ``` albo z tekstem dookoła); None, gdy brak."""
    dec = json.JSONDecoder()
    tekst = str(tekst or "")
    for m in re.finditer(r"\{", tekst):
        try:
            o, _ = dec.raw_decode(tekst[m.start():])
        except ValueError:
            continue
        if isinstance(o, dict):
            return o
    return None


_PARA = re.compile(r"^\s*(-?\d{1,5})\s*,\s*(-?\d{1,5})\s*$")


def waliduj(tekst, poz):
    """Odpowiedź modelu -> {"ruch","powod","dlaczego"}. Wszystko spoza zamkniętej listy, pole poza widokiem albo śmieci =
    ruch `czlowiek` + powód. `poz` = (x,y,z) postaci (potrzebne do idz_do)."""
    def czl(powod, dlaczego=""):
        return {"ruch": "czlowiek", "powod": powod, "dlaczego": dlaczego}
    o = wyciagnij_obiekt(tekst)
    if o is None:
        return czl("odpowiedz_nie_json")
    dl = str(o.get("dlaczego", ""))[:DLACZEGO_MAX]
    r = o.get("ruch")
    if not isinstance(r, str) or not r.strip():
        return czl("brak_pola_ruch", dl)
    czesci = r.strip().split(None, 1)
    kom, arg = czesci[0].lower(), (czesci[1] if len(czesci) > 1 else "")
    if kom == "czlowiek":
        return czl("model_wybral_czlowieka", dl)
    if kom == "krok":
        k = arg.strip().upper()
        return {"ruch": f"krok {k}", "powod": None, "dlaczego": dl} if k in KIERUNKI else czl(f"poza_lista: kierunek {arg!r}", dl)
    if kom in ("uzyj_pola", "lina"):
        m = _PARA.match(arg)
        if not m:
            return czl(f"poza_lista: argument {arg!r}", dl)
        dx, dy = int(m.group(1)), int(m.group(2))
        if abs(dx) > WIDOK_X or abs(dy) > WIDOK_Y:
            return czl(f"pole_poza_widokiem: {dx},{dy}", dl)
        return {"ruch": f"{kom} {dx},{dy}", "powod": None, "dlaczego": dl}
    if kom == "idz_do":
        m = _PARA.match(arg)
        if not m or not poz:
            return czl(f"poza_lista: argument {arg!r}", dl)
        x, y = int(m.group(1)), int(m.group(2))
        if abs(x - poz[0]) > WIDOK_X or abs(y - poz[1]) > WIDOK_Y:
            return czl(f"pole_poza_widokiem: {x},{y}", dl)
        return {"ruch": f"idz_do {x},{y}", "powod": None, "dlaczego": dl}
    if kom == "czekaj":
        try:
            s = float(arg.replace(",", ".").strip())
        except ValueError:
            return czl(f"poza_lista: argument {arg!r}", dl)
        if not (0 < s <= CZEKAJ_MAX_S):
            return czl(f"czekaj_poza_zakresem: {s}", dl)
        return {"ruch": f"czekaj {s:g}", "powod": None, "dlaczego": dl}
    return czl(f"poza_lista: {kom!r}", dl)


# --- kontekst (pkt 2 Zachowania) ---
def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _wzgl(p, poz):
    """Punkt z (x,y,z) i przesunięciem względem postaci (tylko to samo piętro)."""
    d = {"x": p[0], "y": p[1], "z": p[2]}
    if p[2] == poz[2]:
        d["dx"], d["dy"] = p[0] - poz[0], p[1] - poz[1]
    return d


def _wczytaj_json(plik):
    try:
        return json.loads(Path(plik).read_text())
    except (OSError, ValueError):
        return None


def przejscia(poz, mapa=None, katalog=KATALOG, promien=PROMIEN_PRZEJSC, maks=12):
    """Znane przejścia pięter w promieniu `promien` pól: z mapy (flaga 2 na tym piętrze = w dół; flaga 2 piętro wyżej nad tym
    polem = w górę), pola startowe z pietra_start.json / pietra_starty_domyslne.json, nauczone dziury (NIE wchodzić)."""
    x0, y0, z0 = poz
    wyn = {"w_dol_z_mapy": [], "w_gore_z_mapy": [], "pola_startowe_znane": [], "dziury_nauczone_nie_wchodzic": []}
    if mapa is not None:
        try:
            for r in range(promien + 1):          # od środka: najbliższe pierwsze
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if max(abs(dx), abs(dy)) != r:
                            continue
                        x, y = x0 + dx, y0 + dy
                        if len(wyn["w_dol_z_mapy"]) < maks and mapa.flagi(x, y, z0) & BEZ_DROGI:
                            wyn["w_dol_z_mapy"].append([dx, dy])
                        if len(wyn["w_gore_z_mapy"]) < maks and z0 > 0 and mapa.flagi(x, y, z0 - 1) & BEZ_DROGI:
                            wyn["w_gore_z_mapy"].append([dx, dy])
        except Exception:
            wyn["blad_mapy"] = True
    for nazwa in ("pietra_start.json", "pietra_starty_domyslne.json"):
        d = _wczytaj_json(Path(katalog) / "trasy" / nazwa)
        for k, v in (d or {}).items():
            try:
                x, y, z = (int(a) for a in k.split(","))
                if z == z0 and _cheb((x, y), (x0, y0)) <= promien and len(wyn["pola_startowe_znane"]) < maks:
                    wyn["pola_startowe_znane"].append({"przejscie": [x - x0, y - y0], "pole_startowe": [v[0] - x0, v[1] - y0],
                                                       "zrodlo": nazwa})
            except Exception:
                continue
    d = _wczytaj_json(Path(katalog) / "trasy" / "dziury_nauczone.json")
    for q in (d or {}).get("dziury", []) if isinstance(d, dict) else []:
        try:
            if q[2] == z0 and _cheb(q, (x0, y0)) <= promien and len(wyn["dziury_nauczone_nie_wchodzic"]) < maks:
                wyn["dziury_nauczone_nie_wchodzic"].append([q[0] - x0, q[1] - y0])
        except Exception:
            continue
    return wyn


def zbuduj_kontekst(rek, snap):
    """Kontekst dla modelu jako dict (tylko to, co spec dopuszcza: BEZ czatu i nicków graczy). `snap` to migawka z miejsca
    zgłoszenia (cavebot._ratunek_kontekst) albo {}; wszystko opcjonalne."""
    poz = tuple(rek.get("poz") or snap.get("poz") or ())
    ctx = {"sygnal": {"kod": rek.get("kod"), "opis": rek.get("opis")}}
    stwory = []
    for s in snap.get("stwory") or ():
        if s.get("gracz"):
            stwory.append({"typ": "gracz", "dx": s.get("dx"), "dy": s.get("dy")})        # bez nicku
        else:
            stwory.append({"nazwa": s.get("nazwa"), "dx": s.get("dx"), "dy": s.get("dy"), "hp": s.get("hp")})
    nazwy = {s["nazwa"] for s in stwory if s.get("nazwa")}
    szczegoly = {}
    for k, v in rek.items():
        if k in ("kod", "opis", "t", "poz", "wolan_h", "ponad_limit", "tryb", "stan", "czas", "id"):
            continue
        if k in ("cel", "x_cel") and isinstance(v, str) and v not in nazwy:
            v = "[ukryte]"                                      # cel ataku mógł być graczem: nick nie idzie do modelu
        szczegoly[k] = v
    ctx["sygnal"]["liczby"] = szczegoly
    ctx["stan_bota"] = snap.get("stan") if snap.get("stan") is not None else rek.get("stan")
    if poz:
        ctx["pozycja"] = list(poz)
        pk = [tuple(p) for p in (snap.get("punkty") or ()) if len(p) >= 3]
        if pk:
            idx = snap.get("idx")
            cel = pk[idx % len(pk)] if isinstance(idx, int) else None
            if cel is not None:
                na_pietrze = [p for p in pk if p[2] == cel[2]]
                ctx["cel"] = {"punkt_trasy": _wzgl(cel, poz), "pietro_docelowe": cel[2],
                              "najblizszy_punkt_na_pietrze_docelowym": _wzgl(min(na_pietrze, key=lambda p: _cheb(p, poz)), poz)
                              if cel[2] == poz[2] else _wzgl(cel, poz)}
            bliskie = sorted(set(pk), key=lambda p: (p[2] != poz[2], _cheb(p, poz) if p[2] == poz[2] else abs(p[2] - poz[2])))[:5]
            ctx["najblizsze_punkty_trasy"] = [_wzgl(p, poz) for p in bliskie]
        ctx["przejscia_pieter_w_promieniu_10"] = przejscia(poz, snap.get("mapa"), snap.get("katalog") or KATALOG)
    ctx["ostatnie_ruchy"] = (snap.get("ruchy") or [])[-10:]
    ctx["hp_mana"] = {k: snap.get(k) for k in ("hp", "max_hp", "mana", "max_mana") if snap.get(k) is not None}
    ctx["stwory_w_widoku"] = stwory[:15]
    ctx["wypad"] = bool(snap.get("wypad"))
    return ctx


def zbuduj_prompt(ctx):
    return ("Sytuacja bota (JSON). Wybierz jeden ruch z listy i odpowiedz obiektem JSON.\n"
            + json.dumps(ctx, ensure_ascii=False, separators=(",", ":")))


# --- zapis ---
def _dopisz(plik, rekord):
    if plik is None:
        return
    try:
        with open(plik, "a") as f:
            f.write(json.dumps(rekord, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _przytnij_zrzuty(katalog, zostaw=ZRZUTY_MAX):
    try:
        for stary in sorted(Path(katalog).glob("*.jpg"))[:-zostaw]:
            stary.unlink(missing_ok=True)
    except OSError:
        pass


def _zrzut_domyslny():
    """Bajty JPEG ekranu sesji gry (ekran.grim, jedna próba, timeout 5 s); w WĄTKU, nie w pętli bota."""
    import ekran  # noqa: PLC0415
    return ekran.grim("jpeg", proby=1)


def _claude_domyslny(timeout):
    """Klasa Claude z mozg.py. Proces bota to `python mozg.py` (moduł __main__): nie importujemy go drugi raz."""
    if TESTY:
        raise RuntimeError("testy: brak wstrzykniętego modelu (prawdziwy claude zabroniony)")
    for nazwa in ("mozg", "__main__"):
        m = sys.modules.get(nazwa)
        if m is not None and hasattr(m, "Claude"):
            return m.Claude("haiku", timeout=timeout)
    import mozg  # noqa: PLC0415   (inny proces, np. serwis.py)
    return mozg.Claude("haiku", timeout=timeout)


class Cien:
    """Jeden na proces (cien()). zglos() wołane z pętli bota: tylko decyzja i start wątku, bez I/O poza jedną linią jsonl
    przy pominięciu. `claude_fab(timeout) -> callable(prompt, system=, obraz=) -> (tekst, meta)`, `zrzut() -> bytes` są
    wstrzykiwalne (testy); domyślnie Claude z mozg.py i ekran.grim."""

    def __init__(self, claude_fab=None, zrzut=None):
        self.claude_fab = claude_fab
        self.zrzut = zrzut
        self._zamek = threading.Lock()
        self.zajety = False
        self.wywolania = collections.deque()      # time.monotonic() rozpoczętych wywołań (okno godziny)
        self.watek = None
        self.ostatni = None                       # ostatni rekord (testy, diagnostyka)
        self._model = None
        atexit.register(self._zabij)

    def _zabij(self):
        """Przy wyjściu procesu: NAJPIERW zabicie procesu claude (osobna grupa, inaczej sierota), potem najwyżej 1 s na zapis
        rekordu przez wątek. Wyjście nie zależy od cienia (STOP, zatrzymaj.sh czeka 3 s); SIGTERM -> KeyboardInterrupt w trakcie
        join nie może przerwać zabicia (przegląd 19.10: 12 s karencji i sierota claude po SIGTERM)."""
        m = self._model
        if m is not None and hasattr(m, "zabij"):
            try:
                m.zabij()
            except BaseException:
                pass
        w = self.watek
        try:
            if w is not None and w.is_alive():
                w.join(WYJSCIE_CZEKAJ_S)
        except BaseException:
            pass

    def zglos(self, rek, kontekst=None, plik_logu=None, limit_h=20, log=print):
        """Decyzja na sygnał `rek` (dict z ratunek._sygnal + id). Zwraca "start" albo powód pominięcia. Nigdy nie rzuca."""
        try:
            with self._zamek:
                if self.zajety:
                    powod = "trwa_pytanie"
                else:
                    t = time.monotonic()
                    while self.wywolania and t - self.wywolania[0] > 3600:
                        self.wywolania.popleft()
                    if rek.get("ponad_limit") or len(self.wywolania) >= max(1, int(limit_h)):
                        powod = "limit_h"
                    else:
                        powod = None
                        self.zajety = True
                        self.wywolania.append(t)
            if powod:
                self._pominiety(rek, plik_logu, powod, log)
                return powod
            try:
                snap = dict(kontekst(rek)) if callable(kontekst) else dict(kontekst or {})
            except Exception as e:     # migawka z pętli bota nie powiodła się: nie pytamy bez kontekstu
                with self._zamek:
                    self.zajety = False
                    if self.wywolania:
                        self.wywolania.pop()
                self._pominiety(rek, plik_logu, "blad_kontekstu", log, blad=repr(e)[:200])
                return "blad_kontekstu"
            w = threading.Thread(target=self._praca, args=(rek, snap, plik_logu, log), name="ratunek-haiku-cien", daemon=True)
            self.watek = w
            w.start()
            return "start"
        except Exception as e:
            try:
                log(f"debug: ratunek haiku_cien błąd {e!r}")
            except Exception:
                pass
            with self._zamek:
                self.zajety = False
            return "blad"

    # --- wewnętrzne ---
    def _rekord(self, rek, **pola):
        h = {"ruch": None, "powod": None, "dlaczego": "", "odpowiedz": "", "czas_wywolania_s": None, "czas_zrzutu_s": None, "blad": None,
             "zrzut": None, "blad_zrzutu": None, "pominiety": None, "wykonano": False, "model": "haiku", "prompt": ""}
        h.update(pola)
        r = {"rekord": "haiku_cien", "id": rek.get("id"), "kod": rek.get("kod"), "poz": rek.get("poz"),
             "czas": time.strftime("%Y-%m-%d %H:%M:%S"), "haiku_cien": h}
        self.ostatni = r
        return r

    def _pominiety(self, rek, plik, powod, log, **pola):
        _dopisz(plik, self._rekord(rek, pominiety=powod, **pola))
        try:
            log(f"[RATUNEK] haiku_cien: sygnał {rek.get('kod')} pominięty ({powod}).")
        except Exception:
            pass

    def _praca(self, rek, snap, plik, log):
        t0 = time.monotonic()
        pola = {}
        try:
            poz = tuple(rek.get("poz") or ())
            katalog_zrzutow = Path(plik).parent / KATALOG_ZRZUTOW if plik is not None else None
            obraz = None
            tz = time.monotonic()
            try:
                if katalog_zrzutow is not None:
                    dane = (self.zrzut or _zrzut_domyslny)()
                    katalog_zrzutow.mkdir(parents=True, exist_ok=True)
                    sciezka = katalog_zrzutow / f"{rek.get('id') or int(time.time())}.jpg"
                    sciezka.write_bytes(dane)
                    _przytnij_zrzuty(katalog_zrzutow)
                    obraz = sciezka
                    pola["zrzut"] = f"{KATALOG_ZRZUTOW}/{sciezka.name}"
            except Exception as e:
                pola["blad_zrzutu"] = repr(e)[:200]
            pola["czas_zrzutu_s"] = round(time.monotonic() - tz, 2)
            prompt = zbuduj_prompt(zbuduj_kontekst(rek, snap))
            pola["prompt"] = prompt[:PROMPT_MAX]
            t1 = time.monotonic()
            try:
                model = (self.claude_fab or _claude_domyslny)(HAIKU_TIMEOUT_S)
                self._model = model
                wynik = model(prompt, system=SYSTEM, obraz=str(obraz) if obraz else None)
                tekst = wynik[0] if isinstance(wynik, tuple) else wynik
                pola["odpowiedz"] = str(tekst)[:ODP_MAX]
                pola.update(waliduj(tekst, poz))
            except Exception as e:
                pola["blad"] = f"{type(e).__name__}: {e}"[:300]
                pola.update(ruch="czlowiek", powod=("timeout" if "timeout" in str(e).lower() else "blad_wywolania"))
            finally:
                self._model = None
            pola["czas_wywolania_s"] = round(time.monotonic() - t1, 2)
        except BaseException as e:           # wątek-demon nie może nic wywrócić ani zostawić zajętego znacznika
            pola.setdefault("blad", f"{type(e).__name__}: {e}"[:300])
            pola.setdefault("ruch", "czlowiek")
            pola.setdefault("powod", "blad_wywolania")
            pola.setdefault("czas_wywolania_s", round(time.monotonic() - t0, 2))
        finally:
            try:
                r = self._rekord(rek, **pola)
                _dopisz(plik, r)
            finally:
                with self._zamek:
                    self.zajety = False
        try:
            h = r["haiku_cien"]
            log(f"[RATUNEK] haiku_cien: {rek.get('kod')} -> {h['ruch']}"
                f"{' (' + h['powod'] + ')' if h['powod'] else ''} w {h['czas_wywolania_s']} s; bez wykonania.")
        except Exception:
            pass


_CIEN = None


def cien():
    global _CIEN
    if _CIEN is None:
        _CIEN = Cien()
    return _CIEN
