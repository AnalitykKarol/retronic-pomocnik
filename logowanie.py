#!/usr/bin/env python3
"""Logowanie i wylogowanie JEDNEJ instancji (21.10, faza K1; spec dane_tibia/SPEC_logowanie_wylogowanie_1021.md).

  RETRONIC_ID=<id> logowanie.py zaloguj       sesja działa, klient na „Enter Game” (albo „Character List”): klik Login, klik Ok, czeka na grę
  RETRONIC_ID=<id> logowanie.py wyloguj       Ctrl+L co ~4 s w spokojnej chwili, po wylogowaniu `sesja_gry.py zamknij`
  RETRONIC_ID=<id> logowanie.py stan-ekranu   jedno słowo: gra | enter_game | character_list | zgon | nieznany  (--json: szczegóły)
  logowanie.py zbuduj --lista <png...> --enter <png...>   odtwarza szablony okien (dane_tibia/logowanie_szablony.npz)

Skrypty: ./zaloguj.sh, ./wyloguj.sh (RETRONIC_ID z środowiska albo pierwszy argument). Opcje: --limit S, --json, --reczny-ok,
dla wyloguj: --czekaj-spokoj S, --zasieg N.

Zasady bezpieczeństwa (incydent 21.10 07:33: Enter wysłany do klienta, który Karol właśnie zalogował, trafił do gry):
  * ŻADNYCH klawiszy w zaloguj (tylko kliki myszy); w wyloguj jeden akord Ctrl+L, i tylko gdy ekran = gra i spokój;
  * zrzut i rozpoznanie ekranu TUŻ PRZED każdym klikiem (po ustawieniu kursora, tuż przed naciśnięciem), klik tylko gdy ekran
    jest dokładnie tym, który oczekujemy; ekran „gra” albo nieznany = klik się nie wykona;
  * odmowa dla instancji ze STOP_RECZNY i bez bota (Karol gra ręcznie), chyba że --reczny-ok;
  * zgon (HP 0 w pamięci) = odmowa i kod 6 (decyzja Karola, Q5 z SPEC_nadzorca_zestawu_1021).

Kody wyjścia: 0 zrobione (albo nic do zrobienia) · 1 limit czasu / porażka · 2 złe użycie · 3 brak sesji · 4 ręczna gra (STOP_RECZNY)
· 5 brak spokoju (walka, potwór obok) · 6 zgon · 7 ekran nierozpoznany · 8 bot działa poza miastem · 9 zalogowano inną postać.

Moduł nie importuje bota przy imporcie; zrzut, mysz, klawisze, rdzeń i zegar są za interfejsem `Port` (testy bez gry).
"""
import fcntl
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import instancja  # noqa: E402

# --- stałe ----------------------------------------------------------------------------------------------------------

ROZMIAR_SZABLONU = (1175, 910)          # rozmiar sesji, na którym zmierzono okna i współrzędne przycisków (F0, 21.10)
PRZYCISK_LOGIN = (588, 594)             # „Login” w oknie „Enter Game”
PRZYCISK_OK = (641, 628)                # „Ok” w oknie „Character List”
DRGANIE_PX = 2                          # losowe przesunięcie kliku (przyciski: Login 165x18, Ok 62x16)
PLIK_SZABLONOW = KATALOG / "dane_tibia" / "logowanie_szablony.npz"
PROG_SZABLONU = 0.97                    # część komórek KAŻDEGO paska zgodnych z szablonem = okno rozpoznane (zmierzone: 1,00)
ROZNICA_OKIEN = 0.40                    # zgodność rozpoznanego okna musi przewyższać zgodność drugiego o tyle (zmierzone: 0,67-0,98)
KOMORKA_L1 = 24                         # komórka zgodna, gdy |dR|+|dG|+|dB| < tyle (0-765); okna są statyczne: zmierzone różnice 0 (grim, bez kompresji)
# paski okien (x0, x1, y0, y1) dla 1175x910: tytuł, przyciski, jednolite pole listy; BEZ pól tekstowych (konto, hasło, nick)
OBSZARY = {
    "character_list": [(413, 763, 255, 275), (610, 746, 615, 640), (430, 735, 330, 580)],
    "enter_game": [(438, 737, 290, 310), (505, 670, 585, 603), (438, 737, 624, 642), (505, 670, 699, 717)],
}
EKRANY_LOGOWANIA = ("enter_game", "character_list")
STANY = ("gra", "enter_game", "character_list", "zgon", "nieznany")

ZGON_ODCZYTY = 3                        # tyle kolejnych odczytów HP == 0 potwierdza zgon (jak cavebot.SMIERC_ODCZYTY)
ZGON_ODSTEP_S = 0.4

LIMIT_ZALOGUJ_S = 90.0
LIMIT_WYLOGUJ_S = 300.0
CZEKAJ_SPOKOJ_S = 120.0                 # wyloguj: tyle czekamy na koniec walki, potem kod 5
ZASIEG_POTWORA = 2                      # potwór (nie gracz) na tym samym piętrze w tej odległości (Chebyshev) = brak spokoju
CZEKAJ_PO_LOGIN_S = 10.0                # po kliknięciu Login: tyle bez drugiego kliku (zmierzone: lista po <= 2,2 s)
CZEKAJ_PO_OK_S = 12.0                   # po kliknięciu Ok: tyle bez drugiego kliku (zmierzone: gra po 0,8 s)
MAX_KLIKOW = 2                          # na przycisk
POTW_GRA = 2                            # kolejne zrzuty „gra” potwierdzające wejście do gry
KROK_S = 0.5                            # odstęp zrzutów podczas czekania
CTRL_L_PIERWSZY_S = 2.0                 # po pierwszym Ctrl+L czekamy tyle (jak prototyp 20.10), potem CTRL_L_CO_S
CTRL_L_CO_S = 4.0

KOD_OK, KOD_BLAD, KOD_UZYCIE, KOD_BRAK_SESJI, KOD_RECZNY, KOD_WALKA, KOD_ZGON, KOD_EKRAN, KOD_BOT, KOD_POSTAC = range(10)


# --- rozpoznanie ekranu (czysta funkcja zrzutu) ----------------------------------------------------------------------

_szablony = None


def szablony():
    """{klasa: [pasek (h, w, 3) float, ...]} z PLIK_SZABLONOW albo None (brak pliku: okna nierozróżnialne)."""
    global _szablony
    if _szablony is None:
        try:
            import numpy as np  # noqa: PLC0415
            z = np.load(PLIK_SZABLONOW)
            _szablony = {k: [z[f"{k}_{i}"].astype(float) for i in range(len(r))] for k, r in OBSZARY.items()}
        except (OSError, KeyError, ValueError):
            _szablony = False
    return _szablony or None


def zgodnosc_okna(obraz, klasa, szab=None):
    """NAJGORSZY pasek okna `klasa`: część jego komórek zgodnych z szablonem (0..1). Minimum, nie średnia: ciemne okno błędu zasłaniające jeden
    pasek zgadza się z nim w ~90% komórek (tło jest takie samo, różni się tekst), a średnia z czterech pasków by to ukryła.
    None bez szablonu albo gdy rozmiar zrzutu != ROZMIAR_SZABLONU."""
    szab = szablony() if szab is None else szab
    if not szab or tuple(obraz.size) != ROZMIAR_SZABLONU:
        return None
    import numpy as np  # noqa: PLC0415
    a = np.asarray(obraz.convert("RGB"), dtype=float)
    najgorszy = 1.0
    for (x0, x1, y0, y1), wz in zip(OBSZARY[klasa], szab[klasa]):
        d = np.abs(a[y0:y1, x0:x1] - wz).sum(axis=2)
        najgorszy = min(najgorszy, float((d < KOMORKA_L1).mean()))
    return najgorszy


def ikony_klienta(obraz):
    """Pasek klienta w grze: niebieska i zielona ikona na górze okna (piksele W-80,17 / W-50,17; tak jak prototyp wylogowania)."""
    rgb = obraz.convert("RGB")
    W = rgb.width
    a, b = rgb.getpixel((W - 80, 17)), rgb.getpixel((W - 50, 17))
    return (a[2] > 150 and a[0] < 60) or (b[1] > 150 and b[0] < 90)


def klasyfikuj(obraz, szab=None, wz_logowania=None):
    """-> (ekran, szczegoly). ekran: gra | enter_game | character_list | nieznany (zgon dokłada stan_ekranu z pamięci gry).
    Okno logowania = tapeta Retronic (rozlaczenie.ekran_logowania) ORAZ okno rozpoznane po paskach (>= PROG_SZABLONU i o ROZNICA_OKIEN
    więcej niż drugie). Tapeta bez rozpoznanego okna (inny rozmiar, okno błędu, „Connecting...”) = nieznany: żadnego kliku."""
    import rozlaczenie  # noqa: PLC0415
    tapeta = rozlaczenie.ekran_logowania(obraz, wz_logowania)
    ikony = ikony_klienta(obraz)
    sz = {"tapeta": tapeta, "ikony": ikony, "rozmiar": list(obraz.size)}
    if tapeta is True:
        cl, eg = zgodnosc_okna(obraz, "character_list", szab), zgodnosc_okna(obraz, "enter_game", szab)
        sz["character_list"], sz["enter_game"] = cl, eg
        if cl is not None and eg is not None:
            if cl >= PROG_SZABLONU and cl - eg >= ROZNICA_OKIEN:
                return "character_list", sz
            if eg >= PROG_SZABLONU and eg - cl >= ROZNICA_OKIEN:
                return "enter_game", sz
        return "nieznany", sz
    if ikony and tapeta is not True:
        return "gra", sz
    return "nieznany", sz


# --- Port: wszystko, co dotyka świata (podmieniane w testach) ---------------------------------------------------------

class Port:
    """Interfejs. Prawdziwa implementacja: PortZywy. Atrapa w testach/test_logowanie.py."""
    id = ""

    def sesja_zyje(self): raise NotImplementedError
    def zrzut(self): raise NotImplementedError                    # PIL.Image RGB; rzuca przy braku zrzutu
    def klik(self, x, y, potwierdz): raise NotImplementedError     # mysz na (x,y), potem potwierdz(); True = kliknięto
    def ctrl_l(self): raise NotImplementedError
    def gracz(self): raise NotImplementedError                    # dict z rdzenia albo None
    def stwory(self): raise NotImplementedError                   # lista z rdzenia albo None
    def nick(self): raise NotImplementedError                     # oczekiwany nick (profil / log klienta) albo None
    def nicki_z_logu(self): raise NotImplementedError             # lista „Connecting to character X” z Retronic.log
    def bot_dziala(self): raise NotImplementedError
    def w_miescie(self): raise NotImplementedError                # miasto albo None (panel.py --json)
    def stop_reczny(self): raise NotImplementedError
    def zamknij_sesje(self): raise NotImplementedError            # (kod, tekst)
    def teraz(self): return time.monotonic()
    def spij(self, s): time.sleep(s)


class Dziennik:
    """logi/logowanie.log (tekst) i logi/logowanie.jsonl (zdarzenia). Nigdy nie rzuca."""

    def __init__(self, katalog, id_, akcja, wypisz=True):
        self.katalog, self.id, self.akcja, self.wypisz = Path(katalog) if katalog else None, id_, akcja, wypisz

    def log(self, tekst):
        wiersz = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.id} {self.akcja}: {tekst}"
        if self.wypisz:
            print(wiersz, flush=True)
        self._dopisz("logowanie.log", wiersz + "\n")

    def zdarzenie(self, typ, **kw):
        self._dopisz("logowanie.jsonl", json.dumps({"t": round(time.time(), 2), "id": self.id, "akcja": self.akcja, "zdarzenie": typ, **kw},
                                                   ensure_ascii=False, default=str) + "\n")
        self._ostatnie(typ, kw)

    def _ostatnie(self, typ, kw):
        """F1 Przegląd: wejście do gry i wylogowanie trafiają do instancje/<id>/ostatnie.json (bot może nie żyć). Nigdy nie rzuca;
        nic poza prawdziwym katalogiem logi/ i poza testami (RETRONIC_TESTY)."""
        if self.katalog is None or os.environ.get("RETRONIC_TESTY"):
            return
        try:
            import ostatnie  # noqa: PLC0415
            ostatnie.zdarzenie_logowania(self.katalog, self.akcja, typ, kw)
        except Exception:                       # noqa: BLE001
            pass

    def _dopisz(self, nazwa, tekst):
        if self.katalog is None:
            return
        try:
            self.katalog.mkdir(parents=True, exist_ok=True)
            with open(self.katalog / nazwa, "a", encoding="utf-8") as f:
                f.write(tekst)
        except OSError:
            pass


# --- stan ekranu (z pamięci gry: zgon) ---------------------------------------------------------------------------------

def odczyt_hp(port):
    try:
        g = port.gracz()
    except Exception:                           # noqa: BLE001  brak rdzenia nie wywraca rozpoznania
        return None
    hp = g.get("hp") if isinstance(g, dict) else None
    return hp if isinstance(hp, (int, float)) and not isinstance(hp, bool) else None


def zgon_w_pamieci(port, odczyty=ZGON_ODCZYTY):
    """True, gdy HP == 0 przez `odczyty` kolejnych odczytów (pojedyncze zero to możliwy fałszywy odczyt, jak SMIERC_ODCZYTY w bocie)."""
    for n in range(odczyty):
        if odczyt_hp(port) != 0:
            return False
        if n + 1 < odczyty:
            port.spij(ZGON_ODSTEP_S)
    return True


def stan_ekranu(port, dz=None):
    """-> (stan, szczegoly). stan: gra | enter_game | character_list | zgon | nieznany.
    zgon = HP 0 w pamięci gry (3 odczyty) na ekranie gry, na liście postaci albo na ekranie nierozpoznanym (po zgonie klient pokazuje
    okno „You are dead” albo lista postaci; okna zgonu nie mierzono na żywo, brak zrzutu: spec §6). Na „Enter Game” pamięć jest
    świeża albo nieaktualna: tam zgon nie jest ogłaszany."""
    try:
        obraz = port.zrzut()
    except Exception as e:                      # noqa: BLE001
        return "nieznany", {"powod": f"brak zrzutu: {e}"}
    ekran, sz = klasyfikuj(obraz)
    sz["ekran"] = ekran
    if ekran != "enter_game" and odczyt_hp(port) == 0 and zgon_w_pamieci(port):
        sz["powod"] = f"HP 0 w pamięci gry (ekran: {ekran})"
        return "zgon", sz
    return ekran, sz


# --- zaloguj -------------------------------------------------------------------------------------------------------------

def _klik_po_rozpoznaniu(port, dz, oczekiwany, xy):
    """Ustawia kursor, robi ŚWIEŻY zrzut i rozpoznanie TUŻ PRZED naciśnięciem; naciska tylko, gdy ekran == oczekiwany."""
    wynik = {}

    def potwierdz():
        try:
            ekran, sz = klasyfikuj(port.zrzut())
        except Exception as e:                  # noqa: BLE001
            wynik["ekran"], wynik["blad"] = "brak_zrzutu", str(e)
            return False
        wynik["ekran"], wynik["szczegoly"] = ekran, sz
        return ekran == oczekiwany

    kliknieto = bool(port.klik(xy[0], xy[1], potwierdz))
    dz.zdarzenie("klik" if kliknieto else "klik_odwolany", oczekiwany=oczekiwany, xy=list(xy), ekran_przed_klikiem=wynik.get("ekran"),
                 szczegoly=wynik.get("szczegoly"), blad=wynik.get("blad"))
    if not kliknieto:
        dz.log(f"klik w {oczekiwany} {xy} ODWOŁANY: tuż przed naciśnięciem ekran = {wynik.get('ekran')}")
    return kliknieto


def zaloguj(port, dz, limit_s=LIMIT_ZALOGUJ_S, reczny_ok=False):
    """Kod wyjścia (patrz nagłówek). Kliknięcia: Login (tylko na „Enter Game”), Ok (tylko na „Character List”)."""
    t0 = port.teraz()
    if not port.sesja_zyje():
        dz.log("brak sesji gry tej instancji (najpierw: sesja_gry.py start)")
        return KOD_BRAK_SESJI
    if port.stop_reczny() and not port.bot_dziala() and not reczny_ok:
        dz.log("odmowa: STOP_RECZNY bez bota = Karol gra ręcznie (wymuś: --reczny-ok)")
        return KOD_RECZNY
    nicki_przed = len(_nicki(port))
    kliki = {"enter_game": 0, "character_list": 0}
    nie_klikaj_do = 0.0
    gra_z_rzedu = 0
    nieznany_od = None
    ostatni = None
    while port.teraz() - t0 < limit_s:
        stan, sz = stan_ekranu(port)
        if stan != ostatni:
            dz.log(f"ekran: {stan}" + (f" ({sz.get('powod')})" if sz.get("powod") else ""))
            dz.zdarzenie("ekran", stan=stan, szczegoly=sz)
            ostatni = stan
        teraz = port.teraz()
        if stan == "gra":
            nieznany_od = None
            if sum(kliki.values()) == 0:
                dz.log("klient już w grze: nic do zrobienia (żadnego kliku)")
                return KOD_OK
            gra_z_rzedu += 1
            if gra_z_rzedu >= POTW_GRA:
                return _potwierdz_wejscie(port, dz, nicki_przed, teraz - t0)
        else:
            gra_z_rzedu = 0
            if stan == "zgon":
                dz.log("odmowa: zgon (HP 0 w pamięci gry); decyzja Karola, żadnych kliknięć")
                return KOD_ZGON
            if stan in EKRANY_LOGOWANIA:
                nieznany_od = None
                xy = PRZYCISK_LOGIN if stan == "enter_game" else PRZYCISK_OK
                if teraz >= nie_klikaj_do:
                    if kliki[stan] >= MAX_KLIKOW:
                        dz.log(f"porażka: {MAX_KLIKOW} kliknięcia w {'Login' if stan == 'enter_game' else 'Ok'} bez skutku "
                               "(zły login/hasło, okno błędu albo serwer odmawia)")
                        return KOD_BLAD
                    if _klik_po_rozpoznaniu(port, dz, stan, xy):
                        kliki[stan] += 1
                        nie_klikaj_do = port.teraz() + (CZEKAJ_PO_LOGIN_S if stan == "enter_game" else CZEKAJ_PO_OK_S)
                        dz.log(f"klik {'Login' if stan == 'enter_game' else 'Ok'} {xy} (nr {kliki[stan]})")
            else:                               # nieznany: żadnego kliku, czekamy (przejście między oknami, „Connecting...”)
                nieznany_od = nieznany_od if nieznany_od is not None else teraz
        port.spij(KROK_S)
    if nieznany_od is not None:
        dz.log(f"limit {limit_s:g} s: ekran nierozpoznany od {port.teraz() - nieznany_od:.0f} s, żadnego kliku")
        return KOD_EKRAN
    dz.log(f"limit czasu {limit_s:g} s: postać nie weszła do gry (kliki: {kliki})")
    return KOD_BLAD


def _nicki(port):
    try:
        return list(port.nicki_z_logu() or [])
    except Exception:                           # noqa: BLE001
        return []


def _potwierdz_wejscie(port, dz, nicki_przed, sekundy):
    """W grze po naszych klikach: sprawdza, KTÓRA postać weszła (log klienta „Connecting to character X”) i zapisuje wynik."""
    oczekiwany = (port.nick() or "").strip() or None
    nicki = _nicki(port)
    zalogowany = nicki[-1] if len(nicki) > nicki_przed else None
    hp = odczyt_hp(port)
    dz.zdarzenie("w_grze", sekundy=round(sekundy, 1), zalogowany=zalogowany, oczekiwany=oczekiwany, hp=hp)
    if zalogowany and oczekiwany and zalogowany.lower() != oczekiwany.lower():
        dz.log(f"UWAGA: w grze postać {zalogowany!r}, oczekiwano {oczekiwany!r} (konto z wieloma postaciami?). Kod {KOD_POSTAC}")
        return KOD_POSTAC
    dz.log(f"zalogowano w {sekundy:.1f} s: {zalogowany or '(brak nowej linii w logu klienta)'}, HP {hp}")
    return KOD_OK


# --- wyloguj -------------------------------------------------------------------------------------------------------------

def spokoj(port, nick, zasieg=ZASIEG_POTWORA, hp_poprzednie=None):
    """(True|False, powód, hp). Spokój = brak walki: żadnego potwora (nie gracza) na piętrze postaci w odległości <= zasieg,
    żadnego stworzenia z bije_nas/atakowany, HP nie spada między odczytami. Nie znam pozycji postaci = brak spokoju (ostrożnie)."""
    g, lista = None, None
    try:
        g, lista = port.gracz(), port.stwory()
    except Exception as e:                      # noqa: BLE001
        return False, f"rdzeń niedostępny: {e}", None
    hp = g.get("hp") if isinstance(g, dict) else None
    if not isinstance(lista, list):
        return False, "brak listy stworzeń", hp
    if hp_poprzednie is not None and isinstance(hp, (int, float)) and hp < hp_poprzednie:
        return False, f"HP spada ({hp_poprzednie} -> {hp})", hp
    wlasne = [s for s in lista if s.get("gracz") and nick and str(s.get("nazwa", "")).lower() == nick.lower()]
    if not wlasne:
        return False, f"nie widzę własnej postaci na liście ({nick!r})", hp
    for s in lista:
        if s in wlasne:
            continue
        if s.get("bije_nas"):
            return False, f"{s.get('nazwa')} bije nas", hp
        if s.get("atakowany"):
            return False, f"atakujemy {s.get('nazwa')}", hp
        if s.get("gracz"):
            continue
        for w in wlasne:
            if s.get("z") == w.get("z") and max(abs(s.get("x", 0) - w.get("x", 0)), abs(s.get("y", 0) - w.get("y", 0))) <= zasieg:
                return False, f"potwór {s.get('nazwa')} w odległości <= {zasieg}", hp
    return True, "spokój", hp


def wyloguj(port, dz, limit_s=LIMIT_WYLOGUJ_S, czekaj_spokoj_s=CZEKAJ_SPOKOJ_S, zasieg=ZASIEG_POTWORA, reczny_ok=False):
    t0 = port.teraz()
    if not port.sesja_zyje():
        dz.log("sesja gry już nie działa: nic do zamknięcia")
        return KOD_OK
    if port.stop_reczny() and not port.bot_dziala() and not reczny_ok:
        dz.log("odmowa: STOP_RECZNY bez bota = Karol gra ręcznie (wymuś: --reczny-ok)")
        return KOD_RECZNY
    stan, sz = stan_ekranu(port)
    dz.log(f"ekran na starcie: {stan}" + (f" ({sz.get('powod')})" if sz.get("powod") else ""))
    dz.zdarzenie("ekran", stan=stan, szczegoly=sz)
    if stan == "zgon":
        dz.log("odmowa: zgon (HP 0 w pamięci gry); decyzja Karola, żadnych klawiszy")
        return KOD_ZGON
    if stan == "nieznany":
        dz.log("odmowa: ekran nierozpoznany, żadnych klawiszy")
        return KOD_EKRAN
    if stan == "gra":
        if port.bot_dziala():
            miasto = port.w_miescie()
            if not miasto:
                dz.log("odmowa: bot działa poza miastem (najpierw ./wroc.sh albo ./zatrzymaj.sh)")
                return KOD_BOT
            dz.log(f"bot działa w mieście ({miasto}): sesja_gry zamknij zatrzyma go i zostawi STOP_RECZNY")
        kod = _petla_ctrl_l(port, dz, t0, limit_s, czekaj_spokoj_s, zasieg)
        if kod != KOD_OK:
            return kod
    else:
        dz.log(f"klient już na ekranie {stan}: tylko zamknięcie sesji")
    # po wylogowaniu natychmiast zamykamy sesję: autoReconnect loguje z powrotem w < 60 s
    kod, tekst = port.zamknij_sesje()
    dz.zdarzenie("zamkniecie", kod=kod, tekst=tekst)
    dz.log(f"sesja_gry zamknij: kod {kod} {tekst}")
    return KOD_OK if kod == 0 else KOD_BLAD


def _petla_ctrl_l(port, dz, t0, limit_s, czekaj_spokoj_s, zasieg):
    nick = port.nick()
    proby = 0
    hp_pop = None
    bez_spokoju_od = None
    while port.teraz() - t0 < limit_s:
        ok, powod, hp = spokoj(port, nick, zasieg, hp_pop)
        hp_pop = hp
        if not ok:
            bez_spokoju_od = bez_spokoju_od if bez_spokoju_od is not None else port.teraz()
            if port.teraz() - bez_spokoju_od >= czekaj_spokoj_s:
                dz.log(f"odmowa: brak spokoju przez {czekaj_spokoj_s:g} s ({powod}); w Tibii nie wylogujesz się w walce")
                dz.zdarzenie("brak_spokoju", powod=powod)
                return KOD_WALKA
            port.spij(1.5)
            continue
        bez_spokoju_od = None
        stan, sz = stan_ekranu(port)
        if stan in EKRANY_LOGOWANIA:
            dz.log(f"wylogowano po {proby} Ctrl+L ({stan})")
            dz.zdarzenie("wylogowano", proby=proby, ekran=stan)
            return KOD_OK
        if stan == "zgon":
            dz.log("zgon w trakcie wylogowania: stop")
            return KOD_ZGON
        if stan == "gra":                       # Ctrl+L tylko na pewnym ekranie gry (nieznany = czekamy, bez klawiszy)
            port.ctrl_l()
            proby += 1
            dz.zdarzenie("ctrl_l", proba=proby)
            if proby % 15 == 1:
                dz.log(f"Ctrl+L (próba {proby})")
        czekaj = CTRL_L_PIERWSZY_S if proby <= 1 else CTRL_L_CO_S
        k = port.teraz()
        while port.teraz() - k < czekaj:        # w trakcie czekania podglądamy ekran: zamykamy sesję możliwie wcześnie
            port.spij(KROK_S)
            try:
                if klasyfikuj(port.zrzut())[0] in EKRANY_LOGOWANIA:
                    dz.log(f"wylogowano po {proby} Ctrl+L")
                    dz.zdarzenie("wylogowano", proby=proby)
                    return KOD_OK
            except Exception:                   # noqa: BLE001
                pass
    dz.log(f"limit czasu {limit_s:g} s: nie udało się wylogować ({proby} prób Ctrl+L)")
    return KOD_BLAD


# --- prawdziwy Port ---------------------------------------------------------------------------------------------------------

class PortZywy(Port):
    def __init__(self, id_):
        self.id = id_
        self.sc = instancja.sciezki(id_, instancja.runtime("/tmp"))
        self._ekran = None

    # sesja i zrzut
    def _gniazdo_wayland(self):
        try:
            nazwa = (Path(self.sc.sesja) / "wayland").read_text().strip()
        except OSError:
            return None
        return nazwa or None

    def sesja_zyje(self):
        g = self._gniazdo_wayland()
        return bool(g) and (Path(instancja.runtime("/tmp")) / g).exists()

    def zrzut(self):
        import io  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        env = dict(os.environ, WAYLAND_DISPLAY=self._gniazdo_wayland() or "")
        for n in range(2):
            try:
                r = subprocess.run(["grim", "-t", "ppm", "-"], env=env, capture_output=True, timeout=4, check=True)
                return Image.open(io.BytesIO(r.stdout)).convert("RGB")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
                if n == 1:
                    raise
                time.sleep(0.3)

    # mysz i klawisze (XTEST na DISPLAY procesu gry tej instancji)
    def ekran_x11(self):
        if self._ekran is None:
            os.environ["RETRONIC_ID"] = self.id          # bot.py czyta instancję przy imporcie
            import bot  # noqa: PLC0415
            self._ekran = bot.ekran_gry()
        return self._ekran

    def klik(self, x, y, potwierdz):
        import random  # noqa: PLC0415
        from Xlib import X, display  # noqa: PLC0415
        from Xlib.ext import xtest  # noqa: PLC0415
        x += random.randint(-DRGANIE_PX, DRGANIE_PX)
        y += random.randint(-DRGANIE_PX, DRGANIE_PX)
        dpy = display.Display(self.ekran_x11())
        try:
            s = dpy.screen()
            if (s.width_in_pixels, s.height_in_pixels) != ROZMIAR_SZABLONU:
                raise RuntimeError(f"ekran X {s.width_in_pixels}x{s.height_in_pixels} != {ROZMIAR_SZABLONU}: współrzędne nie pasują")
            xtest.fake_input(dpy, X.MotionNotify, 0, x=x, y=y)
            dpy.sync()
            time.sleep(0.12)
            if not potwierdz():                          # zrzut i rozpoznanie tuż przed naciśnięciem
                return False
            xtest.fake_input(dpy, X.ButtonPress, 1)
            dpy.sync()
            time.sleep(0.07)
            xtest.fake_input(dpy, X.ButtonRelease, 1)
            dpy.sync()
            return True
        finally:
            dpy.close()

    def ctrl_l(self):
        from Xlib import X, XK, display  # noqa: PLC0415
        from Xlib.ext import xtest  # noqa: PLC0415
        dpy = display.Display(self.ekran_x11())
        try:
            c = dpy.keysym_to_keycode(XK.string_to_keysym("Control_L"))
            l = dpy.keysym_to_keycode(XK.string_to_keysym("l"))
            for ev, k, pauza in ((X.KeyPress, c, .05), (X.KeyPress, l, .06), (X.KeyRelease, l, .04), (X.KeyRelease, c, 0)):
                xtest.fake_input(dpy, ev, k)
                dpy.sync()
                time.sleep(pauza)
        finally:
            dpy.close()

    # rdzeń gry (gniazdo strażnika instancji, tylko odczyt)
    def _zapytaj(self, zadanie):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(str(self.sc.gniazdo))
            s.sendall((json.dumps(zadanie) + "\n").encode())
            odp = json.loads(s.makefile("rb").readline())
        return odp if odp.get("ok") else None

    def gracz(self):
        odp = self._zapytaj({"cmd": "gracz"})
        return odp.get("gracz") if odp else None

    def stwory(self):
        odp = self._zapytaj({"cmd": "stwory"})
        return odp.get("stwory") if odp else None

    def nick(self):
        if os.environ.get("RETRONIC_POSTAC"):
            return os.environ["RETRONIC_POSTAC"].strip()
        try:
            p = (json.loads((Path(self.sc.stan) / "profil.json").read_text()).get("postac") or "").strip()
        except (OSError, ValueError):
            p = ""
        return p or (_nicki(self) or [None])[-1]

    def nicki_z_logu(self):
        try:
            return re.findall(r"Connecting to character (.+?) on ", Path(self.sc.log_klienta).read_text(errors="replace"))
        except OSError:
            return []

    # bot i stan instancji
    def bot_dziala(self):
        return bool(instancja.procesy(r"(mozg|cavebot)\.py", id_=self.id))

    def w_miescie(self):
        try:
            r = subprocess.run([sys.executable, "-I", str(KATALOG / "panel.py"), "--json"], cwd=str(KATALOG), capture_output=True,
                               text=True, timeout=10, env=dict(os.environ, RETRONIC_ID=self.id, RETRONIC_PANEL_CACHE_S="0"))  # 24.10: decyzja z żywych danych, bez wspólnego cache panelu
            return json.loads(r.stdout).get("w_miescie") or None
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return None

    def stop_reczny(self):
        return Path(self.sc.stop_reczny).exists()

    def zamknij_sesje(self):
        try:
            r = subprocess.run([sys.executable, "-I", str(KATALOG / "sesja_gry.py"), "zamknij"], cwd=str(KATALOG), capture_output=True,
                               text=True, timeout=120, env=dict(os.environ, RETRONIC_ID=self.id))
        except subprocess.TimeoutExpired:
            return 124, "przekroczony limit 120 s"
        return r.returncode, (r.stdout.strip()[-300:] + " " + r.stderr.strip()[-200:]).strip()


# --- budowa szablonów i CLI ----------------------------------------------------------------------------------------------------

def zbuduj(pliki_listy, pliki_enter, wyjscie=PLIK_SZABLONOW):
    """Zapisuje paski okien (średnia z podanych zrzutów) do pliku npz. Paski nie obejmują pól tekstowych (konto, hasło, nick)."""
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    wyniki = {}
    for klasa, pliki in (("character_list", pliki_listy), ("enter_game", pliki_enter)):
        obrazy = [np.asarray(Image.open(p).convert("RGB"), dtype=float) for p in pliki]
        if not obrazy:
            raise SystemExit(f"brak zrzutów dla {klasa}")
        for i, (x0, x1, y0, y1) in enumerate(OBSZARY[klasa]):
            wyniki[f"{klasa}_{i}"] = np.mean([o[y0:y1, x0:x1] for o in obrazy], axis=0).round().astype("uint8")
    np.savez_compressed(wyjscie, **wyniki)
    print(f"zapisano {wyjscie} (lista: {len(pliki_listy)}, enter: {len(pliki_enter)} zrzutów)")


def _opcje(argv):
    opt = {"limit": None, "json": False, "reczny_ok": False, "czekaj_spokoj": CZEKAJ_SPOKOJ_S, "zasieg": ZASIEG_POTWORA, "id": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--limit", "--czekaj-spokoj", "--zasieg"):
            i += 1
            try:
                w = float(argv[i])
            except (IndexError, ValueError):
                raise SystemExit(f"{a} wymaga liczby")
            opt[a[2:].replace("-", "_")] = int(w) if a == "--zasieg" else w
        elif a == "--json":
            opt["json"] = True
        elif a == "--reczny-ok":
            opt["reczny_ok"] = True
        elif a.startswith("--"):
            raise SystemExit(f"nieznana opcja {a}")
        elif opt["id"] is None:
            opt["id"] = a
        else:
            raise SystemExit(f"nadmiarowy argument {a}")
        i += 1
    return opt


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("zaloguj", "wyloguj", "stan-ekranu", "zbuduj"):
        print(__doc__)
        return KOD_UZYCIE
    komenda, reszta = argv[0], argv[1:]
    if komenda == "zbuduj":
        if "--lista" not in reszta or "--enter" not in reszta:
            print("użycie: logowanie.py zbuduj --lista <png...> --enter <png...>")
            return KOD_UZYCIE
        a, b = reszta.index("--lista"), reszta.index("--enter")
        lista = reszta[a + 1:b] if a < b else reszta[a + 1:]
        enter = reszta[b + 1:a] if b < a else reszta[b + 1:]
        zbuduj(lista, enter)
        return KOD_OK
    try:
        opt = _opcje(reszta)
        id_ = instancja.sprawdz_id(opt["id"] or os.environ.get("RETRONIC_ID", ""))
    except (SystemExit, ValueError) as e:
        print(e)
        return KOD_UZYCIE
    if not id_:
        print("wymagane RETRONIC_ID (albo id jako pierwszy argument): główna instancja bez ID nie jest obsługiwana")
        return KOD_UZYCIE
    port = PortZywy(id_)
    if komenda == "stan-ekranu":
        if not port.sesja_zyje():
            print("nieznany")
            print("brak sesji gry tej instancji", file=sys.stderr)
            return KOD_BRAK_SESJI
        stan, sz = stan_ekranu(port)
        print(json.dumps({"stan": stan, **sz}, ensure_ascii=False, default=str) if opt["json"] else stan)
        return KOD_OK
    dz = Dziennik(port.sc.logi, id_, komenda)
    Path(port.sc.stan).mkdir(parents=True, exist_ok=True)
    with open(Path(port.sc.stan) / "logowanie.lock", "a") as zamek:     # jedna akcja logowania/wylogowania naraz na instancję
        try:
            fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            dz.log("odmowa: inna akcja logowania/wylogowania tej instancji trwa")
            return KOD_BLAD
        dz.zdarzenie("start", opcje={k: v for k, v in opt.items() if k != "id"})
        try:
            if komenda == "zaloguj":
                kod = zaloguj(port, dz, opt["limit"] or LIMIT_ZALOGUJ_S, opt["reczny_ok"])
            else:
                kod = wyloguj(port, dz, opt["limit"] or LIMIT_WYLOGUJ_S, opt["czekaj_spokoj"], opt["zasieg"], opt["reczny_ok"])
        except Exception as e:                  # noqa: BLE001
            dz.log(f"BŁĄD: {type(e).__name__}: {e}")
            kod = KOD_BLAD
        dz.zdarzenie("koniec", kod=kod)
        return kod


if __name__ == "__main__":
    sys.exit(main())
