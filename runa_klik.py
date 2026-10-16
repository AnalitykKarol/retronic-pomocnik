#!/usr/bin/env python3
"""Strzał runą kliknięciami (zamiast hotkeya F4, który w tym kliencie nie działa).

Kolejność: prawy klik na runie w plecaku -> pozycja "Use with" w menu kontekstowym -> lewy klik na polu
moba w widoku gry. Strzał nie kosztuje many (mana tylko przy robieniu runy).

Założenia (bez nich nie da się tego sprawdzić na sucho):
 - Pozycję runy w plecaku daje odczyt {"cmd":"kontenery"} (slot = indeks widocznego pola okna) i geometria
   uh.geometria_z_obrazu (to samo, co robi uh.py przy przeciąganiu).
 - Pozycję "Use with" wykrywamy z obrazu: zrzut obszaru pod kursorem po prawym kliku, OCR (tesseract,
   skala x3) i szukanie wiersza z wyrazami "use" + "with". Gdy OCR zawiedzie, klikamy w ostatnio
   znany offset od punktu kliknięcia (albo domyślny RUNA_MENU_DX/RUNA_MENU_DY = drugi wiersz menu).
   Uwaga: gdy menu nie mieści się przy krawędzi ekranu, klient przesuwa je; wtedy działa tylko OCR.
 - Po wybraniu "Use with" kursor jest celownikiem; lewy klik na polu moba oddaje strzał.
 - Weryfikacja: licznik runy w plecaku spadł albo zniknęła, albo HP celu spadło/cel zniknął.
   Brak efektu = Escape (anulowanie celownika) i wynik "bez_efektu"; powtarzaniem rządzi wołający
   (limit porażek + chłodzenie), tu jest jedna próba.

Całość jest wstrzykiwana przez `env`, więc testy chodzą na atrapach bez X11.
"""
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

RUNA_ID = 3198              # HMM (blank rune to 3147)
ID_POJEMNIKOW_RUN = {2868}  # Purple backpack: pojemnik na runy (jak loot.ID_POJEMNIKOW_RUN)
NAZWY_POJEMNIKOW_RUN = ("purple backpack",)
MENU_DX, MENU_DY = 28, 22   # domyślny offset "Use with" od punktu prawego kliku (drugi wiersz menu)
WERYFIKACJA_S = 1.6         # czas na potwierdzenie strzału
OBSZAR_MENU = (-12, -12, 230, 190)   # obszar zrzutu menu względem punktu kliknięcia (x0, y0, x1, y1)
SKALA_OCR = 3


# --- OCR menu -----------------------------------------------------------------
def znajdz_use_with(tsv):
    """Z wyjścia `tesseract ... tsv` -> (x, y) środka wiersza "Use with" w pikselach obrazu OCR albo None."""
    wiersze = {}
    for l in tsv.splitlines()[1:]:
        c = l.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        try:
            klucz = (c[2], c[3], c[4])
            wiersze.setdefault(klucz, []).append(
                (int(c[6]), int(c[7]), int(c[8]), int(c[9]), re.sub(r"[^a-z]", "", c[11].lower())))
        except ValueError:
            continue
    for slowa in wiersze.values():
        slowa.sort()
        t = [s[4] for s in slowa]
        for i in range(len(t) - 1):
            if t[i] in ("use", "usc", "uso") and t[i + 1] in ("with", "wth", "witn"):
                x0 = slowa[i][0]
                x1 = slowa[i + 1][0] + slowa[i + 1][2]
                y = slowa[i][1] + slowa[i][3] // 2
                return (x0 + x1) // 2, y
    return None


def ocr_use_with(obraz, x, y, obszar=OBSZAR_MENU, skala=SKALA_OCR):
    """Szuka "Use with" w menu pod punktem (x, y) zrzutu. -> (px, py) w współrzędnych zrzutu albo None."""
    from PIL import ImageOps
    sz, wy = obraz.size
    x0, y0 = max(0, x + obszar[0]), max(0, y + obszar[1])
    x1, y1 = min(sz, x + obszar[2]), min(wy, y + obszar[3])
    if x1 - x0 < 20 or y1 - y0 < 10:
        return None
    wycinek = obraz.convert("L").crop((x0, y0, x1, y1))
    if sum(wycinek.getdata()) / max(1, wycinek.size[0] * wycinek.size[1]) < 110:   # jasny tekst na ciemnym
        wycinek = ImageOps.invert(wycinek)
    wycinek = wycinek.resize((wycinek.size[0] * skala, wycinek.size[1] * skala))
    with tempfile.TemporaryDirectory() as d:
        plik = Path(d) / "menu.png"
        wycinek.save(plik)
        w = subprocess.run(["tesseract", str(plik), "stdout", "--psm", "6", "tsv"],
                           capture_output=True, text=True, timeout=8)
    p = znajdz_use_with(w.stdout)
    if p is None:
        return None
    return x0 + round(p[0] / skala), y0 + round(p[1] / skala)


# --- losowość kliknięcia "na siebie" (PK_UH_SZYBKIE, R3e) ------------------------------
SIGMA_POLA = 1 / 6          # sigma rozkładu normalnego jako ułamek rozmiaru pola postaci
ODSTEP_CTRL_MS = (60, 180)  # losowy odstęp Ctrl+klik runy -> klik w siebie


def losowy_offset_pola(rng, szer, wys, sigma=SIGMA_POLA):
    """(ox, oy) w pikselach od środka pola o rozmiarze szer x wys: rozkład normalny (sigma = sigma*rozmiar), obcięty do
    pola (nigdy poza nie; próbkowanie z odrzucaniem, po 8 próbach przycięcie do krawędzi)."""
    def os_(rozmiar):
        pol = rozmiar / 2.0
        for _ in range(8):
            v = rng.gauss(0.0, sigma * rozmiar)
            if abs(v) <= pol:
                return v
        return max(-pol, min(pol, v))
    return os_(szer), os_(wys)


def losowy_odstep_ctrl(rng, zakres_ms=ODSTEP_CTRL_MS):
    """Losowy odstęp (s) między Ctrl+klikiem runy a klikiem w siebie."""
    return rng.uniform(zakres_ms[0], zakres_ms[1]) / 1000.0


# --- logika strzału -------------------------------------------------------------
def _rodzaj(k):
    """"plecak" (backpack/bag), "runy" (pojemnik na runy: Purple backpack, id 2868) albo None."""
    nazwa = (k.get("nazwa") or "").casefold()
    if nazwa in ("backpack", "bag"):
        return "plecak"
    if k.get("id") in ID_POJEMNIKOW_RUN or nazwa.startswith(NAZWY_POJEMNIKOW_RUN):
        return "runy"
    return None


def _runy_w(kontenery, runa_id):
    """[(rodzaj, indeks slotu, ilość)] run w pojemniku na runy (najpierw) i w plecaku, kolejność slotów."""
    wynik = []
    for rodzaj in ("runy", "plecak"):
        for k in kontenery or []:
            if _rodzaj(k) != rodzaj:
                continue
            for p in sorted(k.get("przedmioty", []), key=lambda p: p["slot"]):
                if p.get("id") == runa_id:
                    wynik.append((rodzaj, p["slot"], p.get("ilosc", 1)))
    return wynik


def _plecak_runa(kontenery, runa_id):
    """(indeks slotu, ilość) pierwszej runy w plecaku/torbie albo None (bez pojemnika na runy)."""
    r = [x for x in _runy_w(kontenery, runa_id) if x[0] == "plecak"]
    return (r[0][1], r[0][2]) if r else None


def _ilosc(kontenery, runa_id):
    """Łączna ilość run danego ID w plecakach i pojemniku na runy (0 = nie ma)."""
    n = 0
    for k in kontenery or []:
        if _rodzaj(k) is None:
            continue
        for p in k.get("przedmioty", []):
            if p.get("id") == runa_id:
                n += p.get("ilosc", 1)
    return n


def strzel(env, cel, runa_id=RUNA_ID, menu_dx=MENU_DX, menu_dy=MENU_DY, weryfikacja_s=WERYFIKACJA_S,
           szybko=False, ctrl=False, rng=None, budzet_s=1.0):
    """Jedna próba strzału. env: kontenery(), geometria(), prawy(x,y), lewy_pole(dx,dy), zrzut(),
    hp_celu(id) -> % albo None (znikł), klawisz(nazwa), zegar(), spij(s), log(t), pamiec (dict: ostatni offset).
    cel: {"id","dx","dy","hp"}. -> {"wynik": ..., "powod": ...}; wynik: ok | brak_runy | brak_geometrii |
    bez_menu | bez_efektu | blad.
    szybko=True (PK_UH_SZYBKIE): weryfikacja skrócona (spadek ilości run albo wzrost własnego HP z env.hp_wlasne()),
    menu niepotwierdzone = krótki powtórny odczyt, potem wynik "bez_menu" BEZ zgadywania offsetu (dopuszczony tylko
    offset zmierzony wcześniej z OCR, env.pamiec), klik "na siebie" losowo w polu postaci (env.lewy_siebie(rng)),
    ctrl=True: Ctrl+klik runy (env.ctrl_lewy) zamiast menu; całość w budżecie budzet_s."""
    kont = env.kontenery()
    if not kont:
        return {"wynik": "blad", "powod": "brak odczytu kontenerow"}
    kandydaci = _runy_w(kont, runa_id)
    if not kandydaci:
        return {"wynik": "brak_runy", "powod": f"brak runy {runa_id} w plecaku"}
    ilosc0 = _ilosc(kont, runa_id)
    g = env.geometria()
    if not g or not (g.get("plecak") or g.get("runy")):
        return {"wynik": "brak_geometrii", "powod": "brak okna plecaka na ekranie"}
    # pierwsza runa, której okno (siatka własnego kontenera) widać i której slot mieści się w oknie
    pozycja = None
    for rodzaj, slot, _ in kandydaci:
        siatka = g.get(rodzaj) or []
        if slot < len(siatka):
            pozycja = siatka[slot]
            break
    if pozycja is None:
        rodzaj, slot, _ = kandydaci[0]
        return {"wynik": "brak_geometrii", "powod": f"slot {slot} poza oknem ({len(g.get(rodzaj) or [])})"}
    sx, sy = pozycja
    hp0 = cel.get("hp")
    if szybko:
        return _strzel_szybko(env, cel, runa_id, sx, sy, ilosc0, weryfikacja_s, ctrl, rng, budzet_s)
    env.prawy(sx, sy)
    env.spij(0.25)                                   # menu musi się narysować
    pozycja = None
    try:
        obraz = env.zrzut()
        if obraz is not None:
            pozycja = env.ocr(obraz, sx, sy)
    except Exception as e:
        if type(e).__name__ == "Zatrzymano":
            raise
        env.log(f"[RUNA-KLIK] OCR menu: {type(e).__name__}: {e}")
    pam = env.pamiec
    if pozycja is not None:
        pam["offset"] = (pozycja[0] - sx, pozycja[1] - sy)
    else:
        off = pam.get("offset") or (menu_dx, menu_dy)
        pozycja = (sx + off[0], sy + off[1])
        env.log(f"[RUNA-KLIK] 'Use with' nie rozpoznane: klikam offset {off}")
    env.lewy(pozycja[0], pozycja[1])
    env.spij(0.15)
    env.lewy_pole(cel["dx"], cel["dy"])
    t_koniec = env.zegar() + weryfikacja_s
    while True:
        env.spij(0.2)
        k2 = env.kontenery()
        if k2 and _ilosc(k2, runa_id) < ilosc0:
            return {"wynik": "ok", "powod": "ubyło runy"}
        hp = env.hp_celu(cel["id"])
        if hp is None:
            return {"wynik": "ok", "powod": "cel zniknął"}
        if hp0 is not None and hp < hp0:
            return {"wynik": "ok", "powod": f"HP celu {hp0:.0f}% -> {hp:.0f}%"}
        if env.zegar() >= t_koniec:
            break
    try:
        env.klawisz("Escape")                        # anuluj celownik, gdyby został
    except Exception as e:
        if type(e).__name__ == "Zatrzymano":
            raise
    return {"wynik": "bez_efektu", "powod": "ani runa, ani HP celu się nie zmieniły"}


def _anuluj(env):
    try:
        env.klawisz("Escape")                        # anuluj celownik / menu, gdyby zostało
    except Exception as e:
        if type(e).__name__ == "Zatrzymano":
            raise


def _strzel_szybko(env, cel, runa_id, sx, sy, ilosc0, weryfikacja_s, ctrl, rng, budzet_s):
    """Wariant PK_UH_SZYBKIE strzelu (R3): krótko, bez zgadywania menu, klik 'na siebie' losowo w polu postaci."""
    import random
    rng = rng or random
    t0 = env.zegar()
    hp_start = None
    hw = getattr(env, "hp_wlasne", None)
    if hw is not None:
        try:
            hp_start = hw()
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
    if ctrl:
        env.ctrl_lewy(sx, sy)                        # Ctrl+klik runy = "Use with" bez menu (UNKNOWN, czy działa w kliencie)
    else:
        env.prawy(sx, sy)
        env.spij(0.12)                               # krótko: menu rysuje się szybko, drugi odczyt gdy nie
        pozycja = None
        for proba in range(2):
            try:
                obraz = env.zrzut()
                if obraz is not None:
                    pozycja = env.ocr(obraz, sx, sy)
            except Exception as e:
                if type(e).__name__ == "Zatrzymano":
                    raise
                env.log(f"[RUNA-KLIK] OCR menu: {type(e).__name__}: {e}")
            if pozycja is not None:
                break
            if proba == 0:
                env.spij(0.1)                        # krótki powtórny odczyt
        pam = env.pamiec
        if pozycja is not None:
            pam["offset"] = (pozycja[0] - sx, pozycja[1] - sy)
        elif pam.get("offset"):
            off = pam["offset"]                      # offset ZMIERZONY wcześniej z OCR (nie zgadnięty)
            pozycja = (sx + off[0], sy + off[1])
            env.log(f"[RUNA-KLIK] 'Use with' niepotwierdzone: zmierzony offset {off}")
        else:
            _anuluj(env)
            return {"wynik": "bez_menu", "powod": "menu 'Use with' niepotwierdzone (2 odczyty), offset nie jest znany"}
        env.lewy(pozycja[0], pozycja[1])
    pauza = losowy_odstep_ctrl(rng)
    zostalo = budzet_s - (env.zegar() - t0) - 0.2
    env.spij(max(0.0, min(pauza, zostalo)))
    lewy_siebie = getattr(env, "lewy_siebie", None)
    if lewy_siebie is not None:
        lewy_siebie(rng)
    else:
        env.lewy_pole(cel["dx"], cel["dy"])
    wer = min(weryfikacja_s, max(0.2, budzet_s - (env.zegar() - t0)))
    t_koniec = env.zegar() + wer
    while True:
        env.spij(0.15)
        k2 = env.kontenery()
        if k2 and _ilosc(k2, runa_id) < ilosc0:
            return {"wynik": "ok", "powod": "ubyło runy"}
        if hw is not None and hp_start is not None:
            try:
                h = hw()
            except Exception as e:
                if type(e).__name__ == "Zatrzymano":
                    raise
                h = None
            if h is not None and h > hp_start + 1.0:
                return {"wynik": "ok", "powod": f"HP własne {hp_start:.0f}% -> {h:.0f}%"}
        if env.zegar() >= t_koniec:
            break
    _anuluj(env)
    return {"wynik": "bez_efektu", "powod": "ani runa, ani HP własne się nie zmieniły"}


# --- prawdziwe środowisko (nie testowane na X11) -----------------------------------
class SrodowiskoKlik:
    """Spina strzel() z grą: gniazdo pomocnika, zrzut ekranu, mysz XTEST (ekran.Mysz)."""

    def __init__(self, postac, zapytaj, log=print, ttl_geometrii=20.0):
        self.postac, self._zapytaj, self.log = postac, zapytaj, log
        self.pamiec = {}
        self._geo = None
        self._ttl = ttl_geometrii

    def zegar(self):
        return time.monotonic()

    def spij(self, s):
        time.sleep(s)

    def kontenery(self):
        try:
            return self._zapytaj({"cmd": "kontenery"}).get("kontenery")
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            return None

    def geometria(self):
        t = self.zegar()
        if self._geo is not None and t - self._geo[0] < self._ttl and self._geo[1].get("plecak"):
            return self._geo[1]
        import uh
        import ekran
        obraz = ekran.zrzut()
        g = uh.geometria_z_obrazu(obraz, self.kontenery())
        if g:
            rozmiar = ekran._rozmiar_ekranu()
            if obraz.size != rozmiar:
                sx, sy = rozmiar[0] / obraz.size[0], rozmiar[1] / obraz.size[1]
                g = {"reka": {k: (round(x * sx), round(y * sy)) for k, (x, y) in g["reka"].items()},
                     "plecak": [(round(x * sx), round(y * sy)) for x, y in g["plecak"]],
                     "runy": [(round(x * sx), round(y * sy)) for x, y in g.get("runy") or []]}
        self._geo = (t, g or {})
        return g

    def prawy(self, x, y):
        import ekran
        with ekran.Mysz() as m:
            m.prawy(x, y, drganie=2)

    def lewy(self, x, y):
        import ekran
        with ekran.Mysz() as m:
            m.lewy(x, y, drganie=1)

    def lewy_pole(self, dx, dy):
        import ekran
        ekran.klik_pola(dx, dy, 1)                   # zwykły klik, bez modyfikatora (celownik "Use with")

    def ctrl_lewy(self, x, y):
        import ekran
        with ekran.Mysz() as m:
            m.lewy(x, y, modyfikator="Control_L", drganie=1)

    def lewy_siebie(self, rng):
        """Klik 'na siebie' (pole 0,0): środek pola postaci + normalny rozkład sigma ~1/6 pola, obcięty do pola."""
        import ekran
        with ekran.Mysz() as m:
            L, T, R, B = ekran.aktualny_prostokat(m.ekran)
            kw, kh = (R - L) / ekran.POLA_X, (B - T) / ekran.POLA_Y
            ox, oy = losowy_offset_pola(rng, kw, kh)
            px, py = ekran.pole_na_ekran(0, 0, (L, T, R, B))
            m.klik(round(px + ox), round(py + oy), 1, None, 0)    # drganie=0: losowość daje rozkład powyżej

    def zrzut(self):
        import ekran
        obraz = ekran.zrzut()
        rozmiar = ekran._rozmiar_ekranu()
        if obraz.size != rozmiar:
            obraz = obraz.resize(rozmiar)
        return obraz

    def ocr(self, obraz, x, y):
        return ocr_use_with(obraz, x, y)

    def hp_celu(self, ident):
        for s in self._zapytaj({"cmd": "stwory", "maks_wiek": 0.0})["stwory"]:
            if s.get("id") == ident:
                return s.get("hp", 100)
        return None

    def klawisz(self, nazwa):
        self.postac.klawisz(nazwa)
