#!/usr/bin/env python3
"""Zmiana spotu po 3. spotkaniu tego samego gracza (26.10, Karol: „bot ma sam zmieniać spot, gdy na spocie spotyka wielokrotnie tego samego
gracza; po 3. spotkaniu postać idzie gdzie indziej”). Spec: dane_tibia/SPEC_spot_gracz_1026.md. Tylko stdlib, bez importu bota.

Dwie strony tej samej funkcji:
  * BOT (cavebot.py `_spot_gracz_tick`, pokrętło SPOT_ZMIANA_PRZY_GRACZU, domyślnie 0): `Licznik` liczy spotkania obcych graczy na spocie
    (trwały plik instancje/<id>/spotkania_graczy.json), a po progu zapisuje ZLECENIE instancje/<id>/spot_gracz_zadanie.json i, dopóki jest
    bezpiecznie (zero potworów w <= 4 polach, HP >= 70 %, bez ucieczki/PK), odświeża w nim `gotowy_t`. Bot sam spotu NIE zmienia
    (restart bota robi nadzorca, jak przy `napraw <id> zmien_spot`), a jego zachowanie na spocie pozostaje bez zmian.
  * NADZORCA (nadzor.py `decyzja_spot_gracz`): czyta zlecenie (`wczytaj_zadanie`), sprawdza świeżość, `gotowy_t`, limity (`limit_ok`) i unikane
    spoty (`unikane_*`), wybiera nowy spot istniejącym `spoty.wybierz` i robi ten sam restart co `zmien_spot`.

Definicja „spotkania” (progi: stałe poniżej, każda z komentarzem):
  obcy gracz = wpis stwora z `gracz`, który nie jest naszą postacią (profil.json wszystkich instancji + NASZE_ZNANE), NPC, widmem, martwym,
  GM-em, wrogiem z wrogowie.json ani graczem z czaszką (te idą ścieżką PK, której ten moduł nie rusza);
  „na spocie” = obiegi Cavebota na piętrze pętli bez wypadu/dojścia/STÓJ/ucieczki/PK (miasto, depo i droga nie liczą się w ogóle);
  jedno spotkanie = nick widoczny łącznie >= MIN_WIDOK_S s w jednym epizodzie; epizod trwa, dopóki przerwy w widoku są krótsze niż PRZERWA_S,
  więc gracz kręcący się obok 10 minut to JEDNO spotkanie, a trzy osobne to trzy epizody rozdzielone >= PRZERWA_S bez niego w widoku.
"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

KAT = Path(__file__).resolve().parent
if str(KAT) not in sys.path:
    sys.path.insert(0, str(KAT))         # python3 -I nie dodaje katalogu skryptu

PLIK_LICZNIKA = "spotkania_graczy.json"       # instancje/<id>/: trwały licznik spotkań (bot)
PLIK_ZADANIA = "spot_gracz_zadanie.json"      # instancje/<id>/: zlecenie zmiany spotu (bot pisze, nadzorca czyta i kasuje)

# ---- progi (wartości Karola: SPOTKAN_MAX=3; reszta to wartości robocze do oceny, opis w specyfikacji) ----
SPOTKAN_MAX = 3            # Karol 26.10: po 3. spotkaniu tego samego gracza postać zmienia spot
PRZERWA_S = 300            # >= tyle sekund bez nicku w widoku kończy epizod; następne zobaczenie to NOWE spotkanie (~5 min wg Karola)
MIN_WIDOK_S = 15           # nick musi być widoczny łącznie tyle sekund w epizodzie, żeby epizod był spotkaniem (mignięcie nie liczy)
MAX_KROK_S = 10            # dwa kolejne obiegi z nickiem dalej niż tyle sekund od siebie: czas pomiędzy nie liczy się do widoku (luka w pracy bota)
STARZENIE_H = 12           # wpis gracza starszy niż tyle godzin od ostatniego zobaczenia znika z pliku (licznik nie rośnie w nieskończoność)
ZAPIS_CO_S = 20            # wpis „ostatnio widziany” trafia na dysk najwyżej co tyle sekund (zmiana licznika spotkań: od razu)
LIMIT_ODSTEP_S = 1800      # jedna zmiana spotu na postać na 30 min (Karol)
LIMIT_DOBA = 4             # i najwyżej 4 na dobę (Karol): przeciw pętli zmian
LIMIT_DOBA_S = 24 * 3600
UNIKAJ_H = 3               # spot, na którym spotkaliśmy gracza, jest unikany przez tyle godzin (wartość robocza; Karol: „np. 3 h”)
ZADANIE_WAZNE_S = 20 * 60  # zlecenie starsze niż tyle sekund jest przeterminowane (nadzorca go nie wykona; bot po limicie może zlecić nowe)
GOTOWY_SWIEZY_S = 20       # nadzorca wykonuje zlecenie tylko, gdy bot potwierdził „bezpiecznie” nie dalej niż tyle sekund temu
GOTOWY_CO_S = 3            # bot odświeża `gotowy_t` najwyżej co tyle sekund
BEZPIECZNY_ODL = 4         # zmiana tylko gdy żaden żywy potwór nie stoi bliżej niż 5 pól (odl <= 4 blokuje) — Karol
BEZPIECZNY_HP = 70.0       # i HP >= 70 % — Karol
ODL_WIDOKU = 12            # obcy gracz „w polu widzenia” = na tym samym piętrze w tylu polach (Czebyszew); bot dodatkowo zawęża do okna mapy

# nasze postacie spoza profil.json (lista Karola 26.10; profil.json wszystkich instancji dochodzi z dysku)
NASZE_ZNANE = ("Kolanosh", "Kutangen", "Hammburger", "Marinarra", "Geblish", "Wydra", "Pomszta", "Odchyd", "Borsuk", "Invincible",
               "Dawajkesh", "Makumba")
# spoty, na które ta funkcja NIGDY nie przenosi (obok `auto: false` z spoty_nadzorca.json i spotów bez wpisu w tabeli): niebezpieczne wg CLAUDE.md,
# mapy.json i STAN.md (Karol 24.10: z9 pod Kazordoonem; zgon w dziurze thais_pn_z8; wariant z10 Edron bez wpisu w tabeli)
SPOTY_ZAKAZANE = ("trolle_kazordoon_z9", "trolle_kazordoon_z8", "trolle_kazordoon_z7", "thais_pn_z9", "trolle_edron_z10w", "rook_raty_z8_do_smierci",
                  "rook_raty_z9_do_smierci", "rook_cave_raty_z9_glab")

RE_NICK = re.compile(r"\s+")


def klucz(nick):
    """Porównywanie nicków jak obrona_pk.klucz_nicku: bez wielkości liter i nadmiaru spacji."""
    return RE_NICK.sub(" ", str(nick or "").strip()).casefold()


def nasze_nicki(katalog_instancji=None):
    """Zbiór kluczy nicków naszych postaci: profil.json każdej instancji (`postac`) + NASZE_ZNANE. Błędy plików pomijane."""
    kat = Path(katalog_instancji) if katalog_instancji else KAT / "instancje"
    wynik = {klucz(n) for n in NASZE_ZNANE}
    try:
        pliki = list(kat.glob("*/profil.json"))
    except OSError:
        return wynik
    for p in pliki:
        try:
            n = (json.loads(p.read_text(encoding="utf-8")).get("postac") or "").strip()
        except (OSError, ValueError, AttributeError):
            continue
        if n:
            wynik.add(klucz(n))
    return wynik


def _zapis_atomowy(plik, dane):
    """tmp + os.replace w tym samym katalogu. True/False (błąd zapisu nigdy nie wywraca bota)."""
    plik = Path(plik)
    try:
        plik.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=plik.name + ".", suffix=".tmp", dir=str(plik.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dane, f, ensure_ascii=False, indent=1)
        os.replace(tmp, plik)
        return True
    except OSError:
        try:
            os.unlink(tmp)
        except (OSError, UnboundLocalError):
            pass
        return False


def _odczyt(plik):
    try:
        d = json.loads(Path(plik).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# ---------- limity (wspólne: bot liczy zlecenia, nadzorca wykonane zmiany) ----------
def limit_ok(zmiany, teraz):
    """(ok, powód): najwyżej 1 zmiana na LIMIT_ODSTEP_S i LIMIT_DOBA na LIMIT_DOBA_S. `zmiany` = lista epoch (inne wartości pomijane)."""
    ts = sorted(float(t) for t in (zmiany or ()) if isinstance(t, (int, float)) and not isinstance(t, bool))
    doba = [t for t in ts if teraz - t < LIMIT_DOBA_S]
    if ts and 0 <= teraz - ts[-1] < LIMIT_ODSTEP_S:
        return False, f"ostatnia zmiana {int(teraz - ts[-1]) // 60} min temu (limit: 1 na {LIMIT_ODSTEP_S // 60} min)"
    if len(doba) >= LIMIT_DOBA:
        return False, f"{len(doba)} zmian w ostatniej dobie (limit {LIMIT_DOBA})"
    return True, ""


def bezpiecznie(hp_proc, odl_potwora, ucieczka=False, pk_stan=None):
    """Czy wolno teraz zmienić spot: HP >= BEZPIECZNY_HP, najbliższy żywy potwór dalej niż BEZPIECZNY_ODL (None = brak potworów), bez ucieczki i PK.
    Brak odczytu HP = NIE (nie zgadujemy)."""
    if hp_proc is None or hp_proc < BEZPIECZNY_HP:
        return False
    if ucieczka or pk_stan is not None:
        return False
    return odl_potwora is None or odl_potwora > BEZPIECZNY_ODL


# ---------- licznik spotkań (bot) ----------
class Licznik:
    """Trwały licznik spotkań obcych graczy jednej instancji. Czas = epoch (time.time), wstrzykiwany z zewnątrz (testy)."""

    def __init__(self, plik, teraz=None, sesja=None):
        """`plik` None = licznik tylko w pamięci (raport z telemetrii). `sesja` (26.10, Karol: licznik liczy OD OSTATNIEGO ODPALENIA BOTA NA SPOCIE) =
        identyfikator procesu bota; wpisy graczy zapisane przez INNĄ sesję (albo bez klucza `sesja`) są przy wczytaniu pomijane. None = stare zachowanie
        (licznik trwały przez 12 h, przeżywa restart)."""
        self.plik = Path(plik) if plik is not None else None
        self.sesja = sesja
        self.zresetowano = None     # po wczytaniu: sesja poprzedniego zapisu, jeśli licznik wyzerowano z powodu nowej sesji
        self.gracze = {}            # klucz -> {"nick","spotkan","pierwsze_t","ostatnio_t","epizod_od_t","widok_s","zaliczone","mapa"}
        self.zadania = []           # epoch zleceń zmiany spotu (limity 1/30 min, 4/dobę), tylko ostatnia doba
        self._prev_t = None         # czas poprzedniego AKTYWNEGO obiegu (do liczenia czasu widoku)
        self._prev_set = set()      # klucze widoczne w poprzednim aktywnym obiegu
        self._zapis_t = 0.0
        self._brudny = False
        self.wczytaj(time.time() if teraz is None else teraz)

    def wczytaj(self, teraz):
        d = (_odczyt(self.plik) if self.plik is not None else None) or {}
        gr = d.get("gracze") if isinstance(d.get("gracze"), dict) else {}
        if self.sesja is not None and gr and d.get("sesja") != self.sesja:
            self.zresetowano = d.get("sesja") or "brak klucza sesja"
            gr = {}                 # inna sesja bota (restart procesu): spotkania liczymy od zera; limity zmian (`zadania`) zostają
            self._brudny = True
        self.gracze = {}
        for k, e in gr.items():
            if not isinstance(e, dict):
                continue
            try:
                ost = float(e["ostatnio_t"])
                wpis = {"nick": str(e.get("nick") or k), "spotkan": max(0, int(e.get("spotkan", 0))),
                        "pierwsze_t": float(e.get("pierwsze_t", ost)), "ostatnio_t": ost,
                        "epizod_od_t": float(e.get("epizod_od_t", ost)), "widok_s": max(0.0, float(e.get("widok_s", 0.0))),
                        "zaliczone": bool(e.get("zaliczone", False)), "mapa": str(e.get("mapa") or "")}
            except (KeyError, TypeError, ValueError):
                continue
            if teraz - ost <= STARZENIE_H * 3600:
                self.gracze[klucz(k)] = wpis
        zad = d.get("zadania") if isinstance(d.get("zadania"), list) else []
        self.zadania = [float(t) for t in zad if isinstance(t, (int, float)) and not isinstance(t, bool) and teraz - float(t) < LIMIT_DOBA_S]

    def zapisz(self, teraz, wymus=False):
        if self.plik is None or not (wymus or (self._brudny and teraz - self._zapis_t >= ZAPIS_CO_S)):
            return False
        ok = _zapis_atomowy(self.plik, {"v": 1, "zapis_t": teraz, "sesja": self.sesja, "gracze": self.gracze, "zadania": self.zadania,
                                         "_opis": "licznik spotkań obcych graczy na spocie (spot_gracz.py); wpisy starzeją się po "
                                                  f"{STARZENIE_H} h bez widoku"})
        if ok:
            self._zapis_t, self._brudny = teraz, False
        return ok

    def obserwuj(self, teraz, widoczni, aktywny, mapa=""):
        """Jeden obieg bota. `widoczni` = nicki obcych graczy w widoku; `aktywny` = bot na spocie (poza wypadem/dojściem/miastem/STÓJ/ucieczką).
        -> lista nicków, którym ten obieg dopisał kolejne spotkanie. Obieg nieaktywny niczego nie zalicza i zrywa ciągłość czasu widoku."""
        if not aktywny:
            self._prev_t, self._prev_set = None, set()
            return []
        zdarzenia = []
        krok_ok = self._prev_t is not None and 0 <= teraz - self._prev_t <= MAX_KROK_S
        krok = (teraz - self._prev_t) if krok_ok else 0.0
        teraz_set = set()
        for nick in widoczni or ():
            k = klucz(nick)
            if not k or k in teraz_set:
                continue
            teraz_set.add(k)
            e = self.gracze.get(k)
            if e is None or teraz - e["ostatnio_t"] >= PRZERWA_S or teraz < e["ostatnio_t"] - 60:
                # nowy epizod (pierwsze zobaczenie, przerwa >= PRZERWA_S albo zegar cofnięty o > 1 min)
                e = {"nick": str(nick).strip(), "spotkan": e["spotkan"] if e else 0, "pierwsze_t": e["pierwsze_t"] if e else teraz,
                     "ostatnio_t": teraz, "epizod_od_t": teraz, "widok_s": 0.0, "zaliczone": False, "mapa": mapa}
                self.gracze[k] = e
                self._brudny = True
            elif k in self._prev_set:
                e["widok_s"] += krok
            e["ostatnio_t"] = teraz
            if mapa:
                e["mapa"] = mapa
            self._brudny = True
            if not e["zaliczone"] and e["widok_s"] >= MIN_WIDOK_S:
                e["zaliczone"] = True
                e["spotkan"] += 1
                zdarzenia.append(e["nick"])
                self.zapisz(teraz, wymus=True)
        self._prev_t, self._prev_set = teraz, teraz_set
        self.zapisz(teraz)
        return zdarzenia

    def kandydat(self, teraz):
        """(klucz, nick, spotkań) gracza z liczbą spotkań >= SPOTKAN_MAX (najwięcej, potem najświeższy) albo None. Nie sprawdza limitów."""
        wsz = [(e["spotkan"], e["ostatnio_t"], k) for k, e in self.gracze.items() if e["spotkan"] >= SPOTKAN_MAX]
        if not wsz:
            return None
        _, _, k = max(wsz)
        return k, self.gracze[k]["nick"], self.gracze[k]["spotkan"]

    def zlec(self, teraz, klucz_gracza):
        """Zapis zlecenia: licznik tego gracza od zera (po zmianie spotu zaczyna od nowa; przy odmowie nadzorcy kolejna próba dopiero po kolejnych
        SPOTKAN_MAX spotkaniach i po limicie), czas zlecenia do limitów. -> (nick, spotkań)."""
        e = self.gracze[klucz_gracza]
        nick, ile = e["nick"], e["spotkan"]
        e["spotkan"] = 0            # `zaliczone` zostaje True: trwający epizod już się wykorzystał (nie liczy się drugi raz)
        self.zadania = [t for t in self.zadania if teraz - t < LIMIT_DOBA_S] + [teraz]
        self._brudny = True
        self.zapisz(teraz, wymus=True)
        return nick, ile


# ---------- zlecenie (bot pisze, nadzorca czyta) ----------
def zapisz_zadanie(katalog, teraz, nick, spotkan, mapa="", sesja=None):
    """instancje/<id>/spot_gracz_zadanie.json. `gotowy_t` ustawia bot osobno (`odswiez_gotowy`), dopóki jest bezpiecznie."""
    return _zapis_atomowy(Path(katalog) / PLIK_ZADANIA, {"v": 1, "t": teraz, "nick": nick, "spotkan": spotkan, "mapa": mapa, "sesja": sesja, "gotowy_t": None})


def odswiez_gotowy(katalog, teraz):
    """Bot potwierdza „teraz jest bezpiecznie” (zlecenie istnieje i jest ważne). True, gdy zapisano."""
    p = Path(katalog) / PLIK_ZADANIA
    d = _odczyt(p)
    if not d or not isinstance(d.get("t"), (int, float)) or teraz - d["t"] > ZADANIE_WAZNE_S:
        return False
    d["gotowy_t"] = teraz
    return _zapis_atomowy(p, d)


def wczytaj_zadanie(katalog, teraz):
    """-> (zlecenie albo None, powód). Ważne = poprawny JSON z `t`, `nick`, młodszy niż ZADANIE_WAZNE_S."""
    p = Path(katalog) / PLIK_ZADANIA
    if not p.exists():
        return None, "brak zlecenia"
    d = _odczyt(p)
    if not d or not isinstance(d.get("t"), (int, float)) or not str(d.get("nick") or "").strip():
        return None, "zlecenie nieczytelne"
    if teraz - d["t"] > ZADANIE_WAZNE_S:
        return None, f"zlecenie przeterminowane ({int(teraz - d['t']) // 60} min)"
    return d, ""


def gotowe(zad, teraz):
    """Czy bot potwierdził bezpieczeństwo w ciągu GOTOWY_SWIEZY_S."""
    g = zad.get("gotowy_t")
    return isinstance(g, (int, float)) and not isinstance(g, bool) and 0 <= teraz - g <= GOTOWY_SWIEZY_S


def usun_zadanie(katalog):
    try:
        (Path(katalog) / PLIK_ZADANIA).unlink()
        return True
    except OSError:
        return False


# ---------- unikane spoty (nadzorca; lista w jego stanie: [{"mapa","jaskinia","nick","do"}]) ----------
def unikane_aktywne(lista, teraz):
    return [u for u in (lista or []) if isinstance(u, dict) and isinstance(u.get("do"), (int, float)) and u["do"] > teraz and u.get("mapa")]


def unikane_dodaj(lista, mapa, jaskinia, nick, teraz):
    """Dopisuje spot do unikanych na UNIKAJ_H godzin (ten sam spot i nick: odświeża termin). -> nowa lista (stare wygasłe wypadają)."""
    nowe = [u for u in unikane_aktywne(lista, teraz) if not (u.get("mapa") == mapa and klucz(u.get("nick")) == klucz(nick))]
    nowe.append({"mapa": mapa, "jaskinia": jaskinia or mapa, "nick": nick, "do": teraz + UNIKAJ_H * 3600})
    return nowe[-20:]


def zadanie_z_innej_sesji(zad, sesja):
    """True, gdy zlecenie zapisała inna sesja bota niż `sesja` (albo nie ma klucza `sesja`): licznik, z którego powstało, już nie istnieje."""
    return sesja is not None and zad.get("sesja") != sesja


def zadanie_sprzed_startu(zad, start_bota_ep):
    """Nadzorca: zlecenie starsze niż start bieżącego bota (`start_bota_ep` = epoch startu z nazwy logu, z dokładnością do minuty) jest z poprzedniej sesji.
    Prawdziwe zlecenie powstaje najwcześniej po 2 przerwach PRZERWA_S od startu, więc zaokrąglenie do minuty nie ucina żadnego ważnego."""
    return start_bota_ep is not None and zad["t"] < start_bota_ep
