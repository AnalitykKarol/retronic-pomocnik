"""Wypad do miasta po pochodnie (i jedzenie): bot sam wraca do sklepu Al Dee, kupuje, wraca na łowisko.

Wyzwalacze (sprawdzane tylko w spokoju: brak celu, brak zwłok do zebrania, nic nie ucieka):
  A. pochodnie: w plecaku 0 zapasowych, a pochodnia w slocie jest w OSTATNIM etapie (ID z pochodnia_ids.json:
     największe ID "zapalona"), wypalona albo slot pusty; HP >= 70%, brak żywych mobów w promieniu 8.
  B. jedzenie: w plecaku 0 sztuk jedzenia (albo próba jedzenia właśnie padła na braku), HP < 50%, powyżej progu
     ucieczki, brak żywych mobów w promieniu 8 przez >= 10 s.
Oba wymagają potwierdzenia w dwóch kolejnych odczytach (co SPRAWDZ_S). Wypad kupuje WYPAD_ZAKUPY (torch; ham usunięty 11.10: Al Dee go nie sprzedaje)
do celu, niezależnie od tego, który wyzwalacz go zaczął.

Trasa: trasy/do_miasta.json (z piętra 11 do sklepu na z7), powrót = odwrócony koniec do_miasta (z7 -> z8)
+ trasy/z_miasta.json. Zmiany pięter wynikają z mapy (mapa.py), nie z zgadywania:
  w górę (z maleje): LINA. Stoimy obok pola-liny R=(land.x, land.y-1, z), używamy liny na R, lądujemy
                     w (R.x, R.y+1, z-1). Zweryfikowane dla wszystkich czterech przejść do_miasta.
  w dół:             DZIURA. Dziura leży na polu o tych samych x,y co lądowanie, na piętrze wyżej (flaga mapy
                     "no-pathing"); wchodzimy na nią strzałką, ląduje się na polu-linie piętro niżej. Jedyne
                     przejście bez flagi (z7 -> z8, (32060,32173,7), prawdopodobnie właz/kratka) próbujemy:
                     Use z sąsiedniego pola, wejście strzałką, Use na własnym polu; zawsze z odczytem z.
                     Rampy/schody w dół leżą o pole wyżej niż lądowanie (19.10: Edron, rampa (33167,31812,7) ->
                     (33167,31813,8)): po planowanym polu próbujemy sąsiednich pól z flagą mapy 2 w promieniu 1,
                     wolnych od graczy. Etap przejścia bez postępu przez WYPAD_ETAP_MAX_S kończy się awarią (log + powiadomienie).
Chodzenie po jednym piętrze to ta sama maszyneria co zwykła trasa (Cavebot._idz_odcinek: A*, klik, utknięcia).

Bezpieczeństwo: STOP / STOP_RECZNY / ALARM_GM przerywają wypad natychmiast i nie wznawiają go samoczynnie;
ucieczka (HP) ma pierwszeństwo, po niej wypad wraca do najbliższego punktu trasy; limit czasu wypadu,
limity prób na każdym kroku, po porażkach bot wraca na łowisko "po ciemku" z powiadomieniem.
"""

import contextlib
import json
import os
import random
import re
import time
from pathlib import Path

import bot
import marsz_klik

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"
PLIK_IDS = KATALOG / "pochodnia_ids.json"

NPC = "Al Dee"
ID_TORCH = {2920}                       # niezapalona pochodnia (pochodnia.ID_NOWA)
ID_LINA = 3003                          # rope (loot.NAZWA_ID)
ID_LOPATA = 3457                        # shovel (ID klienta, jak rope 3003 / ham 3582; 2554 to ID serwera): odkopanie zasypanej dziury (Use with)
ID_JEDZENIE_DOMYSLNE = {3582, 3583, 3577, 3578, 3579, 3600, 3602, 3607, 3601}   # gdy loot.py niedostępny
NAZWY_PRZEDMIOTOW = {"torch": "torch", "ham": "ham"}   # klucz WYPAD_ZAKUPY -> słowo w "buy N ..."
ID_PRZEDMIOTOW_DOMYSLNE = {"torch": ID_TORCH, "ham": {3582}}

SPRAWDZ_S = 15.0            # co ile (spokój) czytamy ekwipunek/plecak w poszukiwaniu wyzwalacza
POTWIERDZ = 2               # tyle kolejnych odczytów z warunkiem = start
HP_START_POCHODNIE = 70.0   # % HP gracza, od którego wolno wyjść po pochodnie
MOBY_ODL = 8                # pola: żywy potwór tak blisko blokuje start
MAX_CZAS_S = 1500.0         # twardy limit całego wypadu
PO_SUKCESIE_S = 120.0       # po udanym wypadzie nie zaczynamy następnego (zapas czasu na odczyt)
PO_PORAZCE_S = 900.0        # po nieudanym wypadzie
PO_PORAZKACH_S = 3600.0     # po MAX_PORAZEK nieudanych z rzędu: gramy "po ciemku"
MAX_PORAZEK = 2
ETAP_UTK_S = 60.0           # s bez postępu w etapie = utknięcie
ETAP_NIEOSIAG_S = 12.0      # s bez postępu, po których sprawdzamy A*, czy koniec etapu jest w ogóle osiągalny stąd
OSIAG_MAX_PRZESIADEK = 3     # tyle przesiadek na osiągalny punkt bez postępu, potem utknięcie (bez ping-ponga)
OSIAG_KAND = 10             # tylu najbliższych (Chebyshev) punktów planu sprawdzamy A* przy szukaniu osiągalnego
# Dojście do planu drogą patrolu (WYPRAWA_DOJSCIE_PATROLEM, 15.10): postać stoi w części jaskini, z której żaden punkt planu
# nie jest osiągalny po tym samym piętrze (inna strona schodów, kieszeń). Droga = graf przejść pięter z pliku miejsc
# patrolu (Cavebot._patrol_droga) + pietra.py, chodzenie = Cavebot._idz_segment (jak patrol).
DOJSCIE_KAND = 40           # tylu najbliższych (z karą za piętro) punktów planu bierzemy jako cele dojścia
DOJSCIE_PIETRO_KARA = 14    # pola doliczane do odległości kandydata za każde piętro różnicy (jak PATROL_PIETRO_KARA)
DOJSCIE_LIMIT_S = (45.0, 2.5)   # limit marszu jednego planu dojścia: stała + mnożnik * długość drogi (jak PATROL_LIMIT_S)
DOJSCIE_PRZEJSCIE_S = 40.0  # s dodawane do limitu za każde przejście pięter na drodze
DOJSCIE_MAX_S = 600.0       # twardy limit całego dojścia (wszystkie plany razem)
DOJSCIE_PLANY_MAX = 6       # tyle planów dojścia na wyprawę (start + ponowne po nieudanym przejściu / odcinku); zejście z drogi się nie liczy
KLIK_MOB_ODL = 3            # WYPRAWA_MARSZ_KLIK: żywy mob (nie gracz) tak blisko postaci albo ścieżki kliku = bez kliku, rządzi dotychczasowa logika
KLIK_HP_SPADEK = 5.0        # pp HP gracza, o które musi spaść HP w trakcie marszu klikiem, by go przerwać (ktoś nas bije)
KLIK_BLAD_PAUZA_S = 8.0     # s bez prób kliku po kliku, który nic nie ruszył (krok strzałką jak dotąd)
ETAP_PRZEJSCIE_PROB = 6     # prób przejścia pięter (lina/dziura) zanim uznamy awarię
PRZEJSCIE_ODSTEP = (1.0, 3.0, 6.0, 8.0)   # s przerwy między kolejnymi próbami
DRZWI_PROB = 6              # prób otwarcia i wejścia w drzwi (typ etapu DRZWI), potem awaria jak przy linie/dziurze
DRZWI_ODSTEP = (1.5, 3.0, 4.0)   # s przerwy między kolejnymi próbami przy drzwiach
DRZWI_CZEKAJ_S = (0.6, 1.0)      # s oczekiwania po Use na drzwiach (zanim sprawdzimy otwarcie / zrobimy krok)
DRZWI_DALEKO_MAX = 3        # tyle razy "stoi za daleko od drzwi" zanim awaria (nigdy pętla bez końca)
AWARIA_PO_S = 120.0         # utknięcie w mieście na dziurze: ponawiamy co tyle
WYPAD_ETAP_MAX_S = 60.0     # s w etapie przejścia (LINA/DZIURA) bez zmiany pozycji i bez nowej próby = awaria (19.10: 20 min ciszy)
ODP_NPC_S = 6.0             # s czekania na odpowiedź NPC
WERYF_S = 9.0               # s czekania na wzrost liczby sztuk po "yes"
NPC_PROBY = 3               # tyle razy "hi" bez odpowiedzi, zanim sklep uznamy za nieosiągalny
SKLEP_PAUZA_NPC_S = 8.0     # s przerwy między próbami "hi" bez odpowiedzi

ODP_POWITANIE = re.compile(r"hello|welcome|please come in|hi there|greetings|how can i help", re.I)
ODP_PYTANIE = re.compile(r"do you want to (buy|sell)", re.I)
ODP_BRAK_ZLOTA = re.compile(r"not have enough|enough gold|can'?t afford|cannot afford|no gold|"
                            r"not enough money|too expensive", re.I)
ODP_BRAK_MIEJSCA = re.compile(r"capacity|\bcap\b|too heavy|carry|no room|not enough room|backpack is full|"
                              r"container is full|no space", re.I)    # 13.10 (wyprawa.py): przed ODP_BRAK_ZLOTA ("not have enough")
ODP_ODMOWA = re.compile(r"do not sell|don'?t sell|not selling|do not have|don'?t have|"
                        r"sorry|can'?t sell|cannot sell|what\?|do not understand|don'?t understand", re.I)


class BrakEkranu(Exception):
    """Nie widać na ekranie okna plecaka z liną / pola (nie liczy się jako awaria sprzętu)."""


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# --- budowa planu -------------------------------------------------------------

def zbuduj_etapy(punkty, mapa=None, drzwi=()):
    """Lista punktów (x,y,z) -> etapy: {"typ":"IDZ","punkty":[...]} (jedno piętro) przedzielone przejściami
    {"typ":"LINA","stoi","cel","ladunek"} (w górę), {"typ":"DZIURA","stoi","dziura","ladunek","pewna"} albo
    {"typ":"DRZWI","stoi","drzwi"} (zamknięte drzwi na trasie; `drzwi` = zbiór pól (x,y,z)). Kafelek drzwi
    zaczyna następny etap IDZ (po otwarciu bot staje na nim i idzie dalej)."""
    drzwi = {(int(d[0]), int(d[1]), int(d[2])) for d in (drzwi or ())}
    etapy, biez = [], []
    for p in punkty:
        p = (int(p[0]), int(p[1]), int(p[2]))
        if biez and p in drzwi and p[2] == biez[-1][2] and biez[-1] != p:
            a = biez[-1]
            if cheb(a, p) > 1:
                # nagranie bywa rzadkie (co 2 pola): pole stania = sąsiad drzwi na prostej od poprzedniego punktu
                dx, dy = a[0] - p[0], a[1] - p[1]
                if dx == 0 or dy == 0 or abs(dx) == abs(dy):
                    q = (p[0] + (dx > 0) - (dx < 0), p[1] + (dy > 0) - (dy < 0), p[2])
                    biez.append(q)
            etapy.append({"typ": "IDZ", "punkty": biez})
            etapy.append({"typ": "DRZWI", "stoi": biez[-1], "drzwi": p})
            biez = [p]
        elif biez and p[2] != biez[-1][2]:
            a, b = biez[-1], p
            etapy.append({"typ": "IDZ", "punkty": biez})
            if b[2] < a[2]:
                etapy.append({"typ": "LINA", "stoi": a, "cel": (b[0], b[1] - 1, a[2]), "ladunek": b})
            else:
                h = (b[0], b[1], a[2])
                fl = None
                if mapa is not None:
                    try:
                        fl = mapa.flagi(*h)
                    except Exception:
                        fl = None
                etapy.append({"typ": "DZIURA", "stoi": a, "dziura": h, "ladunek": b,
                              "pewna": bool(fl and fl & 2)})
            biez = [b]
        elif not biez or biez[-1] != p:
            biez.append(p)
    if biez:
        etapy.append({"typ": "IDZ", "punkty": biez})
    return etapy


def drzwi_z_mapy(punkty, mapa):
    """Pola trasy (jedno piętro z sąsiadem przed i po na tym samym piętrze), które mapa uważa za nieprzechodnie
    (ściana/woda): to zamknięte drzwi nagrane przez gracza. Mapa niedostępna / pole niewidziane = nic."""
    wynik = set()
    if mapa is None:
        return wynik
    pts = [(int(p[0]), int(p[1]), int(p[2])) for p in punkty]
    for i in range(1, len(pts) - 1):
        a, p, b = pts[i - 1], pts[i], pts[i + 1]
        if a[2] != p[2] or b[2] != p[2]:
            continue
        try:
            if mapa.flagi(*p) & 1 and mapa.przechodnie(*p) is False:
                wynik.add(p)
        except Exception:
            continue
    return wynik


def zbuduj_plan(do, z, mapa=None):
    """(etapy_do, etapy_z): do = punkty do_miasta, z = punkty z_miasta (bez brakującego początku)."""
    do = [(int(p[0]), int(p[1]), int(p[2])) for p in do]
    z = [(int(p[0]), int(p[1]), int(p[2])) for p in z]
    zmiany = [i for i in range(len(do) - 1) if do[i][2] != do[i + 1][2]]
    prefix = []
    if zmiany:
        t = zmiany[-1]
        a, b = do[t], do[t + 1]
        r = (b[0], b[1] - 1, a[2])             # pole-lina: ląduje się w (r.x, r.y+1, z-1) = b
        prefix = list(reversed(do[t + 1:])) + [r, a]
    pts = prefix + z
    return zbuduj_etapy(do, mapa), zbuduj_etapy(pts, mapa)


def wczytaj_plan(katalog=TRASY, mapa=None):
    katalog = Path(katalog)
    do = json.loads((katalog / "do_miasta.json").read_text())
    z = json.loads((katalog / "z_miasta.json").read_text())
    return zbuduj_plan(do, z, mapa)


# Plany wypadu wybierane po położeniu postaci (13.10). "prefix": plan nagrany jak do_miasta/z_miasta (zbuduj_plan:
# powrót odtworzony z końcówki do_miasta); w pozostałych z_miasta jest kompletne (zbuduj_etapy). "npc": sprzedawca
# toreb w tym mieście (None = NPC z konstruktora Wypad, czyli Al Dee). Pliki generuje generuj_trase_miasta.py.
PLANY = (
    {"nazwa": "rook", "do": "do_miasta.json", "z": "z_miasta.json", "npc": None, "prefix": True},
    {"nazwa": "troll", "do": "troll_do_miasta.json", "z": "troll_z_miasta.json", "npc": "Gorn", "prefix": False},
    {"nazwa": "thais_kanaly", "do": "thais_kanaly_do_miasta.json", "z": "thais_kanaly_z_miasta.json",
     "npc": "Gorn", "prefix": False},
)
PLAN_ZASIEG = 40                        # pola: plan pasuje, gdy ma punkt na piętrze postaci nie dalej niż tyle


def wczytaj_plany(katalog=TRASY, mapa=None, plany=PLANY):
    """{nazwa: {"etapy": (do, z), "npc": str|None, "punkty": [...]}} dla planów, których pliki istnieją i są poprawne."""
    katalog = Path(katalog)
    wynik = {}
    for p in plany:
        try:
            do = json.loads((katalog / p["do"]).read_text())
            z = json.loads((katalog / p["z"]).read_text())
            if p.get("prefix"):
                etapy = zbuduj_plan(do, z, mapa)
            else:
                etapy = (zbuduj_etapy([tuple(q) for q in do], mapa), zbuduj_etapy([tuple(q) for q in z], mapa))
            wynik[p["nazwa"]] = {"etapy": etapy, "npc": p.get("npc"),
                                 "punkty": [(int(q[0]), int(q[1]), int(q[2])) for q in do]}
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
    return wynik


def wybierz_plan(plany, poz, zasieg=PLAN_ZASIEG):
    """Nazwa planu z najbliższym punktem do_miasta na piętrze `poz` (<= zasieg pól), albo None."""
    najl = None
    for nazwa, p in plany.items():
        d = min((cheb(poz, q) for q in p["punkty"] if q[2] == poz[2]), default=None)
        if d is not None and d <= zasieg and (najl is None or d < najl[0]):
            najl = (d, nazwa)
    return najl[1] if najl else None


def sprawdz_plan(etapy, mapa=None, drzwi=()):
    """Lista problemów planu (pusta = ok): przejścia obok pola liny/dziury/drzwi, stoi na ostatnim punkcie etapu.
    Kafelki drzwi (etapy DRZWI i lista `drzwi`) są przechodnie, nawet gdy mapa uważa je za ścianę."""
    bledy = []
    for i, e in enumerate(etapy):
        if e["typ"] == "DRZWI":
            if cheb(e["stoi"], e["drzwi"]) > 1:
                bledy.append(f"etap {i}: stoi {e['stoi']} nie sąsiaduje z drzwiami {e['drzwi']}")
            if i + 1 < len(etapy) and etapy[i + 1]["typ"] == "IDZ" and tuple(etapy[i + 1]["punkty"][0]) != tuple(e["drzwi"]):
                bledy.append(f"etap {i}: po drzwiach {e['drzwi']} etap zaczyna się w {etapy[i + 1]['punkty'][0]}")
        elif e["typ"] == "LINA":
            if cheb(e["stoi"], e["cel"]) > 1:
                bledy.append(f"etap {i}: stoi {e['stoi']} nie sąsiaduje z liną {e['cel']}")
        elif e["typ"] == "DZIURA":
            if cheb(e["stoi"], e["dziura"]) > 1:
                bledy.append(f"etap {i}: stoi {e['stoi']} nie sąsiaduje z dziurą {e['dziura']}")
        elif i + 1 < len(etapy) and etapy[i + 1]["typ"] != "IDZ" and e["punkty"][-1] != etapy[i + 1]["stoi"]:
            bledy.append(f"etap {i}: koniec {e['punkty'][-1]} != stoi {etapy[i + 1]['stoi']}")
    return bledy


# --- odczyty / operacje na żywo ----------------------------------------------

def ostatni_etap_pochodni(plik=PLIK_IDS):
    """(ID ostatniego etapu zapalonej, ID wypalonych) z pochodnia_ids.json; domyślnie ({2925}, {2926})."""
    try:
        d = json.loads(Path(plik).read_text())
        zap = {int(i) for i in d.get("zapalona", [])}
        wyp = {int(i) for i in d.get("wypalona", [])}
        return ({max(zap)} if zap else {2925}), (wyp or {2926})
    except (OSError, ValueError, TypeError, AttributeError):
        return {2925}, {2926}


class OperacjeZywe:
    """Odczyt pamięci przez gniazdo + ekran (XTEST). Nigdy nie woła nic poza tym, co robią pochodnia.py i mozg.py."""

    def __init__(self, zapytaj=None, log=print, wyslij=None, zarejestruj=None):
        self.zapytaj = zapytaj or bot.zapytaj
        self.log = log
        self.wyslij = wyslij            # funkcja(tekst): wpisanie na Default (mozg.wpisz_na_czacie)
        self.zarejestruj = zarejestruj  # funkcja(tekst): Czat.wyslano (nasza wypowiedź nie jest "ręczna")
        self.znacznik = None
        self.epoka = None
        self.id_jedzenia = set(ID_JEDZENIE_DOMYSLNE)
        try:
            import loot  # noqa: PLC0415
            self.id_jedzenia = set(loot.KOLEJNOSC_JEDZENIA)
            self.id_ham = {loot.JEDZENIE_ID["ham"]}
        except Exception:
            self.id_ham = {3582}

    # pamięć
    def ekwipunek(self):
        odp = self.zapytaj({"cmd": "kontenery", "ekwipunek": True})
        if odp.get("blad"):
            raise RuntimeError(odp["blad"])
        e = odp.get("ekwipunek")
        if e is None:
            return None
        return {int(s): v["id"] for s, v in e.items()}

    def plecak(self):
        """Zawartość plecaków: {"id": {id: sztuk}} albo None, gdy plecak nie jest otwarty."""
        import loot  # noqa: PLC0415
        odp = self.zapytaj({"cmd": "kontenery"})
        plecaki = [k for k in (odp.get("kontenery") or []) if loot.czy_plecak(k)]
        if not plecaki:
            return None
        ids = {}
        for k in plecaki:
            for p in k.get("przedmioty", []):
                ids[p["id"]] = ids.get(p["id"], 0) + max(1, p.get("ilosc", 1))
        return {"id": ids}

    def wiadomosci(self):
        """Nowe wiadomości od ostatniego odczytu (pierwszy odczyt tylko ustawia znacznik): lista
        {"autor","tekst","kanal","czas","nr"}. Własny znacznik: nie przeszkadza odczytowi Czat w mózgu."""
        z = {"cmd": "wiadomosci", "limit": 100}
        if self.znacznik is not None:
            z.update(od=self.znacznik, epoka=self.epoka)
        odp = self.zapytaj(z)
        pierwszy = self.znacznik is None or odp.get("epoka") != self.epoka
        if odp.get("znacznik") is not None:
            self.znacznik, self.epoka = odp["znacznik"], odp.get("epoka")
        if pierwszy:
            return []
        wynik = []
        for w in odp.get("wiadomosci") or []:
            if isinstance(w, dict):
                autor = w.get("nadawca", w.get("autor", w.get("nazwa")))
                tekst = str(w.get("tekst", w.get("wiadomosc", ""))).strip()
                if tekst:
                    wynik.append({"autor": str(autor or ""), "tekst": tekst,
                                  "kanal": str(w.get("kanal", w.get("typ")) or ""),
                                  "czas": str(w.get("czas") or ""), "nr": w.get("nr")})
        return wynik

    def czat(self, tekst):
        if self.wyslij is None:
            raise RuntimeError("brak funkcji wysyłania na czat")
        if self.zarejestruj is not None:
            self.zarejestruj(tekst)
        self.wyslij(tekst)

    # ekran
    @staticmethod
    def opis_kontenerow(kontenery):
        """Krótki opis otwartych pojemników z pamięci do logu: 'nazwa (id) N rzecz.; ...' (20.10, lina z każdego pojemnika)."""
        if not kontenery:
            return "brak otwartych pojemników"
        return "; ".join(f"{k.get('nazwa') or '?'} (id {k.get('id')}) {len(k.get('przedmioty', []))} rzecz." for k in kontenery)

    def _przedmiot_na_ekranie(self, obraz, id_przedmiotu, nazwa="przedmiotu", wszystkie=False):
        """Środek slotu z przedmiotem o danym ID w oknie plecaka. wszystkie=True (lina, 20.10): gdy w plecakach go nie ma,
        szuka w KAŻDYM otwartym pojemniku z oknem na ekranie (drugi bag, bag na runy, zwłoki); plecaki mają pierwszeństwo,
        więc lina w głównym plecaku działa jak dotąd. Brak: BrakEkranu z listą sprawdzonych pojemników."""
        import loot  # noqa: PLC0415
        okna = loot.znajdz_okna(obraz)
        kontenery, powod = loot.kontenery_z_pamieci()
        if kontenery is None:
            raise BrakEkranu(f"pamięć: {powod}")
        przypisane, powod = loot.dopasuj_okna(obraz, okna, kontenery)
        if przypisane is None:
            gdzie = [k.get("nazwa") for k in kontenery if any(p["id"] == id_przedmiotu for p in k.get("przedmioty", []))]
            raise BrakEkranu(f"okna plecaka: {powod}; pojemniki w pamięci: {self.opis_kontenerow(kontenery)}"
                             + (f"; {nazwa} leży w: {', '.join(map(str, gdzie))}" if gdzie else ""))
        for tylko_plecaki in ((True, False) if wszystkie else (True,)):
            for o, k in zip(okna, przypisane):
                if tylko_plecaki != bool(loot.czy_plecak(k)):
                    continue
                for p in k.get("przedmioty", []):
                    if p["id"] == id_przedmiotu and p["slot"] < len(o.sloty):
                        return o.sloty[p["slot"]].srodek
        poza = [f"{k.get('nazwa')} slot {p['slot']}" for k in przypisane for p in k.get("przedmioty", [])
                if p["id"] == id_przedmiotu]
        raise BrakEkranu(f"nie widzę {nazwa} w oknie plecaka"
                         + ("" if not wszystkie else " ani w innym otwartym pojemniku")
                         + f"; sprawdzone pojemniki: {self.opis_kontenerow(przypisane)}"
                         + (f"; {nazwa} poza widocznym oknem: {', '.join(poza)}" if poza else ""))

    def _lina_na_ekranie(self, obraz):
        return self._przedmiot_na_ekranie(obraz, ID_LINA, "liny (rope)", wszystkie=True)

    def _uzyj_na_polu(self, id_przedmiotu, nazwa, cel, poz, wszystkie=False):
        """Ctrl+klik na przedmiocie w plecaku (Use with), potem klik na polu `cel` (<= 1 pola od `poz`)."""
        import ekran  # noqa: PLC0415
        import loot  # noqa: PLC0415
        dx, dy = cel[0] - poz[0], cel[1] - poz[1]
        if abs(dx) > 1 or abs(dy) > 1:
            raise BrakEkranu(f"pole {nazwa} {cel} za daleko od {tuple(poz)}")
        with ekran.Mysz() as mysz:
            obraz = loot._zrzut(mysz)
            x, y = self._przedmiot_na_ekranie(obraz, id_przedmiotu, nazwa, wszystkie)
            mysz.klik(x, y, 1, "Control_L", drganie=3)
            time.sleep(0.45)
            mysz.klik(*ekran.pole_na_ekran(dx, dy, ekran.aktualny_prostokat(mysz.ekran)), 1, None, drganie=2)

    def uzyj_line(self, cel, poz):
        """Ctrl+klik na linie w plecaku (Use), potem klik na polu `cel` (pole-lina).
        15.10: bez liny w plecaku bierzemy ją ze slotu ekwipunku (zwykle amunicja, slot 10)."""
        try:
            self._uzyj_na_polu(ID_LINA, "liny (rope)", cel, poz, wszystkie=True)
            return
        except BrakEkranu as ex:
            blad = ex
        e = self.ekwipunek() or {}
        slot = next((s for s, i in e.items() if int(i) == ID_LINA), None)
        if slot is None:
            raise BrakEkranu(f"{blad}; ekwipunek (sloty: {sorted(e) or 'brak odczytu'}) bez liny")
        import ekran  # noqa: PLC0415
        import loot  # noqa: PLC0415
        import pochodnia  # noqa: PLC0415
        dx, dy = cel[0] - poz[0], cel[1] - poz[1]
        if abs(dx) > 1 or abs(dy) > 1:
            raise BrakEkranu(f"pole liny {cel} za daleko od {tuple(poz)}")
        with ekran.Mysz() as mysz:
            obraz = loot._zrzut(mysz)
            xy = pochodnia.pozycje_ekwipunku(obraz).get(int(slot))
            if xy is None:
                raise BrakEkranu(f"lina w slocie {slot}, ale nie widzę panelu Inventory")
            mysz.klik(xy[0], xy[1], 1, "Control_L", drganie=3)
            time.sleep(0.45)
            mysz.klik(*ekran.pole_na_ekran(dx, dy, ekran.aktualny_prostokat(mysz.ekran)), 1, None, drganie=2)

    def uzyj_lopate(self, cel, poz):
        """Ctrl+klik na łopacie w plecaku (Use with), potem klik na polu `cel` (zasypana dziura) albo własnym."""
        self._uzyj_na_polu(ID_LOPATA, "łopaty (shovel)", cel, poz)

    def uzyj_pole(self, pole, poz):
        """Ctrl+klik (Use) na polu mapy `pole` względem naszej pozycji `poz`."""
        import ekran  # noqa: PLC0415
        dx, dy = pole[0] - poz[0], pole[1] - poz[1]
        if abs(dx) > 1 or abs(dy) > 1:
            raise BrakEkranu(f"pole {pole} za daleko od {tuple(poz)}")
        ekran.otworz(dx, dy)


# --- maszyna stanów wypadu ----------------------------------------------------

class Wypad:
    """Jeden wypad naraz. Wołany z Cavebot.idz() (więc tylko wtedy, gdy walka, loot i pauzy nic nie chcą):
    tick() -> True, gdy zużył obieg. Stan "SPOKOJ" = brak wypadu."""

    def __init__(self, cb, ops, konf=None, log=print, plan=None, katalog=TRASY, npc=NPC, plik_ids=PLIK_IDS):
        self.cb = cb
        self.ops = ops
        self.konf = konf
        self.log = log
        self.npc = npc
        self.plik_ids = plik_ids
        self.plan = plan
        self._plan_wymuszony = plan is not None   # plan podany z zewnątrz (testy): bez wyboru po położeniu
        self.plany = None                         # {nazwa: plan} wczytane przy pierwszym wypadzie
        self.plan_nazwa = None
        self._npc_domyslny = npc
        self.katalog = katalog
        self.stan = "SPOKOJ"
        self.faza = None            # "do" | "sklep" | "z"
        self.etapy = None
        self.ei = 0
        self.pi = 0
        self.t_start = 0.0
        self.powod = ""
        self.blokada_do = float("-inf")
        self.zablokowany = False    # po STOP/ALARM_GM nie wznawiamy samoczynnie
        self.porazki = 0
        self.sprawdzono = float("-inf")
        self.potw_p = 0             # kolejne potwierdzenia wyzwalacza (pochodnie / jedzenie)
        self.potw_j = 0
        self.spokoj_od = None
        self.ost_obieg = float("-inf")
        self.postep = None          # [czas, wskaznik] postępu w etapie
        self.osiag_proba = float("-inf")    # kiedy ostatnio sprawdzaliśmy A*, czy koniec etapu jest osiągalny
        self.osiag_przesiadki = 0           # przesiadki bez postępu (po OSIAG_MAX_PRZESIADEK: utknięcie)
        self.dojscie = None                 # trwające dojście do planu drogą patrolu (patrz _dojscie_start)
        self.dojscie_plany = 0              # plany dojścia w tej wyprawie (limit DOJSCIE_PLANY_MAX)
        self.dojscie_t0 = None              # początek dojścia (twardy limit DOJSCIE_MAX_S)
        self.dojscie_sprawdz = False        # pierwszy obieg wyprawy: czy z miejsca startu jest w ogóle dojście do planu
        self.utk = 0
        self.wyjatki = 0
        self.przystanek_od = None   # od kiedy stoimy w tym etapie (tolerancja dojścia)
        self.ucieczka_flaga = False
        self.wynik = None
        self.kupione = {}
        self.sklep = None
        self.msg_ost = []
        self.ostrzezenia = set()
        self.awaria_log = float("-inf")
        self._przyst_ei = None
        self.drzwi_otwarte = set()  # kafelki drzwi, które w tym wypadzie już się otworzyły (powrót: najpierw krok)
        self.pj = None              # [klucz, od kiedy]: czy etap przejścia (LINA/DZIURA) robi postęp (_pilnuj_przejscia)
        self.pj_proby = 0           # liczba wykonanych prób przejścia w tym wypadzie (zmiana = postęp)
        self._klik_zakaz_do = float("-inf")   # WYPRAWA_MARSZ_KLIK: do kiedy nie próbujemy kliku (klik bez ruchu, przerwanie)
        self.klik_ile = 0           # udane marsze klikiem w tym wypadzie (do logu)

    # --- konfiguracja (stałe z modułu cavebot: pokrętła ustawiają je w locie) ---

    def _k(self, nazwa, domyslna):
        return getattr(self.konf, nazwa, domyslna) if self.konf is not None else domyslna

    def zakupy(self):
        """[(klucz, cel sztuk)] w kolejności zakupów."""
        z = dict(self._k("WYPAD_ZAKUPY", {"torch": 5}))
        if "torch" in z:
            z["torch"] = max(int(z["torch"]), int(self._k("WYPAD_ILE_TORCHY", 5)))
        return [(k, int(v)) for k, v in z.items() if int(v) > 0]

    # --- pomocnicze ---

    @property
    def aktywny(self):
        return self.stan != "SPOKOJ"

    def _tele(self, typ, **d):
        t = getattr(self.cb, "tele", None)
        if t is not None:
            try:
                t.zdarzenie(typ, **d)
            except Exception:
                pass

    def _powiadom(self, tytul, tresc, pilnosc="normal", klucz="wypad"):
        try:
            import powiadom  # noqa: PLC0415
            powiadom.powiadom(tytul, tresc, pilnosc, klucz)
        except Exception:
            pass

    def _blad(self, typ, **d):
        self.log(f"Wypad: błąd {typ} {d}")
        self._tele("wypad_blad", rodzaj=typ, faza=self.faza, **d)

    def _stop(self):
        bot.sprawdz_stop()
        if not os.environ.get("RETRONIC_TESTY") and bot.STOP.with_name("STOP_RECZNY").exists():
            raise bot.Zatrzymano("plik STOP_RECZNY")

    def _ids(self, klucz):
        ids = getattr(self.ops, "id_przedmiotow", None)
        if ids and klucz in ids:
            return set(ids[klucz])
        if klucz == "ham":
            return set(getattr(self.ops, "id_ham", {3582}))
        return set(ID_PRZEDMIOTOW_DOMYSLNE.get(klucz, ()))

    def _ile(self, plecak, klucz):
        if plecak is None:
            return None
        ids = plecak.get("id", {})
        return sum(n for i, n in ids.items() if i in self._ids(klucz))

    def _jedzenie_ile(self, plecak):
        if plecak is None:
            return None
        ids = set(getattr(self.ops, "id_jedzenia", ID_JEDZENIE_DOMYSLNE))
        return sum(n for i, n in plecak.get("id", {}).items() if i in ids)

    # --- wyzwalacze ---

    def _plan(self):
        if self.plan is None:
            self.plan = wczytaj_plan(self.katalog, getattr(self.cb, "mapa", None))
            for nazwa, etapy in zip(("do_miasta", "z_miasta"), self.plan):
                for b in sprawdz_plan(etapy):
                    self.log(f"Wypad: plan {nazwa}: {b}")
        return self.plan

    def _wybierz_plan(self, poz):
        """Plan dla położenia `poz` (rook / troll / thais_kanaly); brak dopasowania = dawny plan (do_miasta)."""
        if self._plan_wymuszony:
            return self._plan()
        if self.plany is None:
            try:
                self.plany = wczytaj_plany(self.katalog, getattr(self.cb, "mapa", None))
            except Exception as e:
                self.plany = {}
                self._blad("plany", opis=repr(e))
        nazwa = wybierz_plan(self.plany, poz)
        if nazwa is None:
            self.plan = None
            self.plan_nazwa = "rook"
            self.npc = self._npc_domyslny
            return self._plan()
        p = self.plany[nazwa]
        self.plan, self.plan_nazwa = p["etapy"], nazwa
        self.npc = p["npc"] or self._npc_domyslny
        for tytul, etapy in zip(("do_miasta", "z_miasta"), self.plan):
            for b in sprawdz_plan(etapy):
                self.log(f"Wypad: plan {nazwa} {tytul}: {b}")
        self.log(f"Wypad: plan {nazwa} (NPC {self.npc}) dla pozycji {tuple(poz)}")
        return self.plan

    def tick(self):
        """True, gdy obieg zużyty przez wypad."""
        cb = self.cb
        teraz = cb.zegar()
        if self.stan == "SPOKOJ":
            if not self._okazja(teraz):
                return False
        try:
            self._stop()
            wynik = self._obieg(teraz)
            self.wyjatki = 0
            return wynik
        except bot.Zatrzymano:
            self.przerwij("STOP")
            raise
        except Exception as e:
            self.wyjatki += 1
            self._blad("wyjatek", opis=repr(e), n=self.wyjatki)
            cb.pauza(0.5, 1.0)
            if self.wyjatki >= 5:
                self._koniec("blad", "zbyt wiele wyjątków")
            return True

    def _okazja(self, teraz):
        cb = self.cb
        if self.zablokowany or teraz < self.blokada_do:
            return False
        if not self._k("WYPAD_PO_TORCHE", True) and not self._k("WYPAD_JEDZENIE", True):
            return False
        poz = cb.ruch_poz if getattr(cb, "ruch_poz", None) else None
        if poz is None:
            return False
        # spokój od potworów (do wyzwalacza jedzenia)
        lista = getattr(cb, "ostatnie_stwory", [])
        moby = cb._zywe_w_promieniu(lista, poz, MOBY_ODL)
        if moby:
            self.spokoj_od = None
        elif self.spokoj_od is None:
            self.spokoj_od = teraz
        if teraz - self.sprawdzono < self._k("WYPAD_SPRAWDZ_S", SPRAWDZ_S):
            return False
        if cb.cel is not None or cb.ucieczka or moby or getattr(cb, "zwloki_czekajace", None):
            self.potw_p = self.potw_j = 0
            return False
        self.sprawdzono = teraz
        try:
            g = cb.gracz()
            proc = g.get("proc", 100.0)
            ekw = self.ops.ekwipunek()
            plecak = self.ops.plecak()
        except bot.Zatrzymano:
            raise
        except Exception as e:
            if "odczyt" not in self.ostrzezenia:
                self.ostrzezenia.add("odczyt")
                self.log(f"Wypad: odczyt ekwipunku/plecaka nie działa ({e!r})")
            return False
        self.ostrzezenia.discard("odczyt")
        koncowe, wypalone = ostatni_etap_pochodni(self.plik_ids)
        slot = None if ekw is None else ekw.get(10, ekw.get("10"))
        torch = self._ile(plecak, "torch")
        konczy_sie = ekw is not None and (slot is None or slot in koncowe or slot in wypalone)
        a = bool(self._k("WYPAD_PO_TORCHE", True) and plecak is not None and torch == 0 and konczy_sie
                 and proc >= HP_START_POCHODNIE)
        jedz = self._jedzenie_ile(plecak)
        brak_jedz = (jedz == 0) or (jedz is None and teraz < getattr(cb, "jedzenie_nie_do", float("-inf")))
        try:
            cb.jedzenie_plecak = (teraz, jedz)      # czar exevo pan korzysta z tej wiedzy (brak jedzenia w plecaku)
        except Exception:
            pass
        prog = getattr(cb, "prog_aktualny", 40) + 3
        spokoj = self.spokoj_od is not None and teraz - self.spokoj_od >= self._k("WYPAD_JEDZENIE_SPOKOJ_S", 10.0)
        b = bool(self._k("WYPAD_JEDZENIE", True) and brak_jedz and proc < self._k("WYPAD_JEDZENIE_HP", 50.0)
                 and proc > prog and spokoj)
        czar = getattr(cb, "jedzenie_czar_zastepuje_wypad", None)
        if b and czar is not None and czar(g, teraz):
            b = False                    # exevo pan (F3) robi jedzenie: wypad do miasta niepotrzebny
        if plecak is None and "plecak" not in self.ostrzezenia:
            self.ostrzezenia.add("plecak")
            self.log("Wypad: nie widzę otwartego plecaka w pamięci, nie sprawdzę zapasu")
        self.potw_p = self.potw_p + 1 if a else 0
        self.potw_j = self.potw_j + 1 if b else 0
        if self.potw_p >= POTWIERDZ:
            return self._start("pochodnie", {"slot": slot, "torch": torch, "hp": round(proc)})
        if self.potw_j >= POTWIERDZ:
            return self._start("jedzenie", {"jedzenie": jedz, "hp": round(proc)})
        return False

    def _start(self, powod, dane):
        cb = self.cb
        teraz = cb.zegar()
        poz = cb.postac.pozycja()
        try:
            do, z = self._wybierz_plan(poz)
        except Exception as e:
            self._blad("plan", opis=repr(e))
            self.blokada_do = teraz + PO_PORAZCE_S
            return False
        self.etapy = do
        self.faza = "do"
        if not self._resync_globalny(poz):
            self.log(f"Wypad: pozycja {poz} poza trasą do miasta, nie ruszam")
            self._blad("start_poza_trasa", poz=list(poz))
            self.blokada_do = teraz + PO_PORAZCE_S
            self.faza = self.etapy = None
            return False
        self.powod = powod
        self.stan = "WYPAD"
        self.t_start = teraz
        self.kupione = {}
        self.sklep = None
        self.utk = 0
        self.postep = None
        self.pj = None
        self.ostrzezenia = {k for k in self.ostrzezenia if isinstance(k, str)}    # jednorazowe logi etapów (krotki) od nowa
        self.dojscie, self.dojscie_plany, self.dojscie_t0 = None, 0, None
        self.dojscie_sprawdz = True
        self.wyjatki = 0
        self.potw_p = self.potw_j = 0
        cb.wypad_aktywny = True
        cb._wypad_reset_klik()
        try:
            self.ops.wiadomosci()        # znacznik czatu: odpowiedzi NPC tylko od teraz
        except Exception:
            pass
        self.log(f"Wypad: start ({powod}), poz {poz}, zakupy {self.zakupy()}, {dane}")
        self._tele("wypad_start", powod=powod, poz=list(poz), zakupy=dict(self.zakupy()), **dane)
        return True

    # --- główny obieg ---

    def _obieg(self, teraz):
        cb = self.cb
        if teraz - self.t_start > self._max_czas():
            return self._awaria("limit_czasu", f"wypad trwa ponad {self._max_czas():.0f} s")
        poz = cb.postac.pozycja()
        if teraz - self.ost_obieg > 5.0:
            self.postep = None          # luka (walka, ucieczka, loot): nie liczymy jej do utknięcia
            self.pj = None
        cb.ustaw_stan("WYPAD", f"{self.faza} {self.ei}/{len(self.etapy)}")
        try:
            if self.faza == "sklep":
                return self._sklep(poz, teraz)
            return self._idz_faza(poz, teraz)
        finally:
            # luka = odstęp od KOŃCA poprzedniego obiegu, nie od jego początku: obieg z krokiem i czekaniem na
            # klienta trwa ~5 s, więc liczony od początku kasował `postep` w każdym obiegu i utknięcie nie
            # odpalało się nigdy (15.10 20:29: 6+ min oscylacji bez alarmu)
            self.ost_obieg = cb.zegar()

    def uciekaj(self, poz):
        """Wołane z Cavebot.uciekaj podczas wypadu: krok do poprzedniego punktu planu albo pauza."""
        cb = self.cb
        self.ucieczka_flaga = True
        self.postep = None
        try:
            e = self.etapy[self.ei] if self.etapy else None
            if e is not None and e["typ"] == "IDZ" and poz[2] == e["punkty"][0][2]:
                pkt = e["punkty"]
                k = min(range(len(pkt)), key=lambda i: cheb(poz, pkt[i]))
                cel = pkt[max(0, k - 1)]
                if cheb(poz, cel) > 0:
                    cb.krok_do(cel)
                    return True
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            self._blad("ucieczka", opis=repr(ex))
        cb.pauza(0.5, 1.0)
        return True

    # --- pozycja względem planu ---

    def _punkty_pietra(self, z):
        return [(ei, e) for ei, e in enumerate(self.etapy) if e["typ"] == "IDZ" and e["punkty"][0][2] == z]

    def _resync_globalny(self, poz):
        """Najbliższy punkt planu na piętrze gracza (A* wśród kilku najbliższych). False: brak takiego piętra."""
        kand = []
        for ei, e in self._punkty_pietra(poz[2]):
            for pi, p in enumerate(e["punkty"]):
                kand.append((cheb(poz, p), -ei, pi, ei))
        if not kand:
            return False
        kand.sort()
        najlepszy = kand[0]
        cb = self.cb
        if getattr(cb, "mapa", None) is not None and len(kand) > 1:
            najl_d = None
            for _, _, pi, ei in kand[:6]:
                p = self.etapy[ei]["punkty"][pi]
                if (p[0], p[1]) == (poz[0], poz[1]):
                    d = []
                else:
                    try:
                        d = cb.droga(tuple(poz), p[:2], dlugosc=0)
                    except Exception:
                        d = None
                if d is None:
                    continue
                if najl_d is None or len(d) < najl_d[0]:
                    najl_d = (len(d), ei, pi)
            if najl_d is not None:
                _, ei, pi = najl_d
                self.ei, self.pi = ei, pi
                return True
        self.ei, self.pi = najlepszy[3], najlepszy[2]
        return True

    def _resync(self, poz):
        e = self.etapy[self.ei]
        if self.ucieczka_flaga:
            self.ucieczka_flaga = False
            return self._resync_globalny(poz)
        if e["typ"] == "DRZWI":
            if poz[2] == e["stoi"][2]:
                return True
            return self._resync_globalny(poz)
        if e["typ"] in ("LINA", "DZIURA"):
            if poz[2] == e["ladunek"][2]:
                self.ei = min(self.ei + 1, len(self.etapy) - 1)
                self.pi = 0
                self.utk = 0
                self.postep = None
                self.przystanek_od = None
                return True
            if poz[2] == e["stoi"][2]:
                return True
            return self._resync_globalny(poz)
        if poz[2] == e["punkty"][0][2]:
            return True
        return self._resync_globalny(poz)

    # --- chodzenie ---

    def _idz_faza(self, poz, teraz):
        cb = self.cb
        if self.dojscie is not None:
            return self._dojscie_krok(poz, teraz)
        if self.dojscie_sprawdz:
            self.dojscie_sprawdz = False
            if self._dojscie_start(poz, teraz, "start", tylko_gdy_odciety=True):
                return True
        if not self._resync(poz):
            if self._dojscie_start(poz, teraz, "poza_planem"):
                return True
            return self._awaria("zgubiona_pozycja", f"poz {poz} poza planem")
        e = self.etapy[self.ei]
        if e["typ"] == "LINA":
            return self._lina(poz, e, teraz)
        if e["typ"] == "DZIURA":
            return self._dziura(poz, e, teraz)
        if e["typ"] == "DRZWI":
            return self._drzwi(poz, e, teraz)
        pkt = e["punkty"]
        ost = pkt[-1]
        nastepny = self.etapy[self.ei + 1] if self.ei + 1 < len(self.etapy) else None
        # dojście: dokładnie na ostatni punkt albo (po chwili) obok pola liny/dziury / sklepu
        if self.przystanek_od is None or self._przyst_ei != self.ei:
            self.przystanek_od = teraz
            self._przyst_ei = self.ei
        cel_blisko = None
        if nastepny is not None and nastepny["typ"] == "LINA":
            cel_blisko = nastepny["cel"]
        elif nastepny is not None and nastepny["typ"] == "DZIURA":
            cel_blisko = nastepny["dziura"]
        elif nastepny is not None and nastepny["typ"] == "DRZWI":
            cel_blisko = nastepny["drzwi"]
        na_miejscu = tuple(poz) == tuple(ost) or (
            cel_blisko is not None and poz[2] == ost[2] and cheb(poz, cel_blisko) <= 1
            and teraz - self.przystanek_od > 15.0 and cheb(poz, ost) <= 2) or (
            nastepny is None and self.faza == "do" and poz[2] == ost[2] and cheb(poz, ost) <= 1
            and teraz - self.przystanek_od > 25.0)
        if na_miejscu:
            return self._etap_gotowy(e, poz, teraz)
        # utknięcie: brak zbliżenia do końca etapu przez ETAP_UTK_S
        wsk = (self.ei, -cheb(poz, ost) if poz[2] == ost[2] else -999)
        if self.postep is None or wsk > self.postep[1]:
            if self.postep is not None:
                self.osiag_przesiadki = 0
            self.postep = [teraz, wsk]
        elif teraz - self.postep[0] > ETAP_UTK_S:
            return self._utkniecie(poz, e, teraz)
        elif teraz - self.postep[0] > ETAP_NIEOSIAG_S and teraz - self.osiag_proba > ETAP_NIEOSIAG_S:
            self.osiag_proba = teraz
            if self._objazd_nieosiagalny(poz, e, ost, teraz):
                return True
        # WYPRAWA_MARSZ_KLIK=1: w drodze do miasta/depo klik w najdalsze zwykłe pole ścieżki; bez kliku (albo po nim bez ruchu)
        # idzie dotychczasowa maszyneria poniżej
        if self.faza == "do" and int(self._k("WYPRAWA_MARSZ_KLIK", 0)) and self._marsz_klik(poz, pkt, teraz):
            return True
        # krok po odcinku: ta sama maszyneria co zwykła trasa
        wynik, idx = cb._idz_odcinek(pkt, min(self.pi, len(pkt) - 1))
        self.pi = idx
        if wynik is False:
            self.utk += 1
            self._blad("odcinek_nieosiagalny", poz=list(poz), etap=self.ei, n=self.utk)
            if self.utk >= 3:
                self.utk = 0
                return self._utkniecie(poz, e, teraz, wymus=True)
        return True

    # --- marsz klikiem w drodze do miasta (WYPRAWA_MARSZ_KLIK, 20.10) ---

    def _marsz_klik(self, poz, pkt, teraz):
        """Jeden klik w najdalsze pole GĘSTEJ ścieżki odcinka `pkt` (kolejne pola sąsiednie; rzadkie punkty nagrania uzupełnia linia prosta),
        do KLIK_MAKS_POL pól naprzód i w zasięgu widoku. Wszystkie pola ścieżki muszą być zwykłe wg mapy i wolne (bez ognia, bez zajętych
        przez stwory i graczy, widma pomijane), a prostokąt postać + cała ścieżka z marginesem 1 pola nie może zawierać pola z flagą 2
        (schody, dziury, krzesła, nieznane przejścia) ani dziury nauczonej; inaczej ścieżka jest skracana. Min. 2 pola, inaczej kroki.
        Ścieżka startuje ZA punktem planu najbliższym postaci (okno wokół self.pi, remis: bliższy pi; plan z zawrotem ma to samo pole dwa
        razy), urywa się na zawrocie, a klik musi skracać pozostałą drogę liczoną po planie i nie może celować we własne pole.
        Potem czekanie na ruch (marsz_klik.klik_i_czekaj, limit czasu liczony w polach). False (kroki jak dotąd): postać nie stoi na
        odcinku, mob blisko, groźny gracz, ucieczka, mniej niż 2 pola, klik bez ruchu (wtedy KLIK_BLAD_PAUZA_S przerwy) albo klik
        odrzucony (ValueError, 3 s przerwy). True = obieg zużyty: ruch, zmiana piętra (dalej rządzi _resync / etap przejścia) albo
        przerwanie (mob, groźny gracz, spadek HP: Escape, a walkę/ucieczkę podejmuje Cavebot w następnym obiegu jak dotąd)."""
        cb = self.cb
        klik, mp = getattr(cb, "klik", None), getattr(cb, "mapa", None)
        if klik is None or mp is None or teraz < self._klik_zakaz_do:
            return False
        if getattr(cb, "ucieczka", False) or getattr(cb, "ostrozny", False):
            return False
        poz = tuple(poz)
        z = poz[2]
        k = self._klik_indeks(pkt, poz)
        if k is None:
            return False                      # postać zeszła z odcinka: wraca na niego dotychczasowa maszyneria
        gesta = marsz_klik.gesta_sciezka_idx(poz, pkt[k + 1:])
        pola = [xy for xy, _ in gesta]
        if len(pola) < 2:
            return False
        lista = [m for m in (getattr(cb, "ostatnie_stwory", None) or []) if m.get("z") == z and not m.get("widmo")]
        ja = getattr(getattr(cb, "postac", None), "nazwa", None)
        inni = [m for m in lista if m.get("nazwa") != ja]
        if self._klik_zagrozenie(inni, poz):
            return False
        moby = [m for m in inni if not m.get("gracz") and m.get("hp", 100) > 0]
        zajete = {(m["x"], m["y"]) for m in inni if m.get("x") is not None}
        ogien = set()
        try:
            ogien = set(cb._ogien_xy(z))
        except (AttributeError, TypeError):
            pass
        n = marsz_klik.ile_pol_klik(mp, poz, pola, unik=zajete | ogien, zakaz=(ogien, self._klik_dziury(poz, pola)))
        for i in range(n):                    # mob tuż przy ścieżce kliku: klient poprowadziłby postać obok niego
            if any(cheb((m["x"], m["y"]), pola[i]) <= KLIK_MOB_ODL - 1 for m in moby):
                n = i
                break
        if n < 2:
            return False
        cel_kl = (pola[n - 1][0], pola[n - 1][1], z)
        if cel_kl[:2] == poz[:2] or not self._klik_postep(pkt, k, poz, cel_kl, k + 1 + gesta[n - 1][1]):
            self.log(f"Wypad: marsz klikiem: klik na {cel_kl[:2]} z {poz[:2]} nie przybliża do końca odcinka, pomijam")
            self._klik_zakaz_do = teraz + 1.0
            return False
        self.pi = max(self.pi, k)             # wyrównanie indeksu planu do pozycji (kliki przesuwają postać o kilka punktów naraz)
        t0 = cb.zegar()
        try:
            klik(cel_kl[0] - poz[0], cel_kl[1] - poz[1])
        except ValueError:
            self._klik_zakaz_do = teraz + 3.0  # poza widokiem: nie ponawiamy co obieg
            return False
        hp0 = self._klik_hp()
        wynik = marsz_klik.klik_i_czekaj(cb.postac, poz, cel_kl, n, zegar=marsz_klik.Czas(cb.zegar, cb.spij), log=self.log,
                                         przerwij=lambda p: self._klik_przerwij(p, hp0), prefiks="Wypad: marsz klikiem")
        nowa = tuple(cb.postac.pozycja())
        dt = cb.zegar() - t0
        opis = f"klik na {cel_kl[:2]} {n} pól z {poz[:2]}"
        if wynik == "ruch":
            self.klik_ile += 1
            i = self._klik_indeks(pkt, nowa)
            if i is not None:
                self.pi = max(self.pi, i)
            self.log(f"Wypad: marsz klikiem: {opis}: " + (f"doszedł w {dt:.1f} s" if nowa[:2] == cel_kl[:2]
                                                         else f"ruszył, stoję w {nowa[:2]} po {dt:.1f} s"))
            return True
        if wynik == "pietro":
            self.log(f"Wypad: marsz klikiem: {opis}: zmiana piętra po {dt:.1f} s")
            return True
        if wynik == "przerwano":
            self.log(f"Wypad: marsz klikiem: {opis}: przerwany w {nowa[:2]} po {dt:.1f} s (mob, PK albo spadek HP), dalej jak dotąd")
            try:
                cb.postac.klawisz("Escape")   # klient dalej prowadziłby postać do klikniętego pola
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
            self._klik_zakaz_do = teraz + 3.0
            return True
        self.log(f"Wypad: marsz klikiem: {opis}: nic nie ruszył, wracam do kroków na {KLIK_BLAD_PAUZA_S:.0f} s")
        self._klik_zakaz_do = teraz + KLIK_BLAD_PAUZA_S
        return False

    def _klik_indeks(self, pkt, poz):
        """Indeks punktu odcinka najbliższego postaci (to samo piętro, Chebyshev <= 2: pole zagęszczonej ścieżki leży w pobliżu punktu planu),
        szukany w oknie wokół self.pi; przy remisie bliższy self.pi (plan z zawrotem może mieć to samo pole dwa razy: liczy się przejście,
        na którym jesteśmy), potem późniejszy. None = postać poza planem."""
        okno = range(max(0, self.pi - 3), min(len(pkt), self.pi + 12))
        kand = [(cheb(pkt[i], poz), abs(i - self.pi), -i) for i in okno if pkt[i][2] == poz[2] and cheb(pkt[i], poz) <= 2]
        return -min(kand)[2] if kand else None

    @staticmethod
    def _klik_postep(pkt, k, poz, cel, b):
        """Czy klik przybliża do końca odcinka liczonego PO PLANIE: pozostała droga z celu kliku (do punktu `b`, do którego prowadzi jego
        odcinek, plus reszta planu) musi być krótsza niż z pozycji postaci (do punktu `k` plus reszta). Klik 'za siebie' odpada."""
        def reszta(i):
            return sum(cheb(pkt[t], pkt[t + 1]) for t in range(i, len(pkt) - 1) if pkt[t][2] == pkt[t + 1][2])
        return cheb(cel, pkt[b]) + reszta(b) < cheb(poz, pkt[k]) + reszta(k)

    def _klik_dziury(self, poz, pola):
        """Pola (x, y) w prostokącie postać + ścieżka (margines 1), które Cavebot zna jako zmianę piętra albo dziurę nauczoną."""
        cb = self.cb
        fn = [getattr(cb, n, None) for n in ("pole_zmiany_pietra", "dziura_nauczona")]
        fn = [f for f in fn if callable(f)]
        wynik = set()
        if not fn:
            return wynik
        xs, ys = [poz[0]] + [p[0] for p in pola], [poz[1]] + [p[1] for p in pola]
        for x in range(min(xs) - 1, max(xs) + 2):
            for y in range(min(ys) - 1, max(ys) + 2):
                try:
                    if any(f((x, y, poz[2])) for f in fn):
                        wynik.add((x, y))
                except Exception:             # noqa: BLE001  (błąd odczytu mapy = brak informacji, nie klik)
                    return {(x, y) for x in range(min(xs) - 1, max(xs) + 2) for y in range(min(ys) - 1, max(ys) + 2)}
        return wynik

    def _klik_zagrozenie(self, inni, poz):
        """Powód, dla którego nie klikamy: żywy mob (nie gracz) w KLIK_MOB_ODL albo groźny gracz (GM/czaszka) w widoku; None = wolno."""
        groznie = getattr(self.cb, "gracz_grozny", None)
        for m in inni:
            if m.get("x") is None or m.get("hp", 100) <= 0:
                continue
            if m.get("gracz"):
                if callable(groznie) and groznie(m):
                    return "gracz"
            elif cheb((m["x"], m["y"]), poz) <= KLIK_MOB_ODL:
                return "mob"
        return None

    def _klik_hp(self):
        try:
            return float(self.cb.gracz().get("proc", 100.0))
        except Exception:
            return None

    def _klik_przerwij(self, poz, hp0):
        """Odpytywane w trakcie marszu klikiem: True = przerwać (STOP rzuca bot.Zatrzymano). Świeża lista stworów z cache skanera."""
        cb = self.cb
        self._stop()
        hp = self._klik_hp()
        if hp0 is not None and hp is not None and hp < hp0 - KLIK_HP_SPADEK:
            return True
        try:
            lista = cb.stwory(maks_wiek=0.6)
        except (AttributeError, TypeError):
            lista = getattr(cb, "ostatnie_stwory", None) or []
        except bot.Zatrzymano:
            raise
        except Exception:
            return False
        ja = getattr(getattr(cb, "postac", None), "nazwa", None)
        inni = [m for m in lista or [] if m.get("z") == poz[2] and not m.get("widmo") and m.get("nazwa") != ja]
        return self._klik_zagrozenie(inni, poz) is not None

    def _najblizszy_osiagalny(self, poz, pomin_ei):
        """(ei, pi) najbliższego (długość drogi A*) punktu planu na piętrze gracza, do którego `cb.droga` ma
        drogę; etapy późniejsze niż bieżący mają pierwszeństwo przed wcześniejszymi (postęp planu). None: żaden."""
        cb = self.cb
        kand = [(cheb(poz, p), ei, pi) for ei, e in self._punkty_pietra(poz[2]) if ei != pomin_ei
                for pi, p in enumerate(e["punkty"])]
        kand.sort()
        najl = None
        for _, ei, pi in kand[:OSIAG_KAND]:
            p = self.etapy[ei]["punkty"][pi]
            if (p[0], p[1]) == (poz[0], poz[1]):
                dl = 0
            else:
                try:
                    d = cb.droga(tuple(poz), p[:2], dlugosc=0)
                except Exception:
                    d = None
                if d is None:
                    continue
                dl = len(d)
            klucz = (ei < pomin_ei, dl)
            if najl is None or klucz < najl[0]:
                najl = (klucz, ei, pi)
        return None if najl is None else (najl[1], najl[2])

    def _objazd_nieosiagalny(self, poz, e, ost, teraz):
        """Brak postępu >= ETAP_NIEOSIAG_S: gdy A* mówi, że końca etapu nie ma jak osiągnąć z tego miejsca (inna
        drabina, pokój bez wyjścia: gra odpowiada "There is no way"), nie chodzimy ślepo w jego stronę. Przesiadamy
        się na najbliższy osiągalny punkt planu na tym piętrze albo, gdy takiego nie ma, liczymy to utknięciem.
        True = obieg zużyty. False: koniec etapu osiągalny (albo nie umiemy tego ocenić) - chodzimy dalej."""
        cb = self.cb
        if poz[2] != ost[2] or not hasattr(cb, "droga"):
            return False
        try:
            if cb.droga(tuple(poz), ost[:2], dlugosc=1) is not None:
                return False
        except Exception:
            return False
        cel = self._najblizszy_osiagalny(poz, self.ei)
        self._blad("etap_nieosiagalny", poz=list(poz), etap=self.ei, cel=list(cel) if cel else None)
        if cel is None and self._dojscie_start(poz, teraz, "etap_nieosiagalny"):
            return True
        self.osiag_przesiadki += 1
        if cel is None or self.osiag_przesiadki > OSIAG_MAX_PRZESIADEK:
            self.osiag_przesiadki = 0
            return self._utkniecie(poz, e, teraz, wymus=True)
        self.log(f"Wypad: koniec etapu {self.ei} {tuple(ost)} nieosiągalny z {tuple(poz)}; "
                 f"przesiadka na etap {cel[0]} punkt {cel[1]}")
        self.ei, self.pi = cel
        self.postep = None
        self.utk = 0
        self.przystanek_od = None
        self.cb._wypad_reset_klik()
        return True

    # --- dojście do planu drogą patrolu (WYPRAWA_DOJSCIE_PATROLEM) ---

    @contextlib.contextmanager
    def _dojscie_ctx(self):
        """Na czas planowania i chodzenia dojścia Cavebot traktuje przejścia pięter jak w patrolu (`wypad_dojscie`:
        _pietra_wlaczone / _patrol_pietra_ok nie blokują ich przez wypad_aktywny, bez zatrzymań na potworach)."""
        cb = self.cb
        stary = getattr(cb, "wypad_dojscie", False)
        cb.wypad_dojscie = True
        try:
            yield
        finally:
            cb.wypad_dojscie = stary

    def _dojscie_wlaczone(self):
        cb = self.cb
        return bool(int(self._k("WYPRAWA_DOJSCIE_PATROLEM", 1))) and callable(getattr(cb, "_patrol_droga", None)) \
            and callable(getattr(cb, "_idz_segment", None))

    def _dojscie_plan(self, poz):
        """Najkrótsza droga patrolu (Cavebot._patrol_droga: A* po piętrze albo graf przejść pięter/łączników z pliku
        miejsc) z `poz` do któregoś punktu planu. -> (seg, (ei, pi), id użytych przejść) albo None. Remis długości:
        późniejszy etap (postęp planu). Cel: DOJSCIE_KAND najbliższych punktów (co 3. + końce etapów)."""
        cb = self.cb
        if getattr(cb, "miejsca", 1) is None:
            try:
                cb._patrol_wczytaj()            # przejścia pięter i graf z pliku miejsc (PATROL_PLIK)
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
        kand = []
        for ei, e in enumerate(self.etapy or []):
            if e["typ"] != "IDZ":
                continue
            pkt = e["punkty"]
            for pi, p in enumerate(pkt):
                if pi % 3 and pi != len(pkt) - 1:
                    continue
                if (p[0], p[1], p[2]) == tuple(poz[:3]):
                    continue
                kand.append((cheb(poz, p) + DOJSCIE_PIETRO_KARA * abs(p[2] - poz[2]), -ei, pi, ei))
        kand.sort()
        najl = None
        with self._dojscie_ctx():
            for _, _, pi, ei in kand[:DOJSCIE_KAND]:
                p = self.etapy[ei]["punkty"][pi]
                uz = []
                try:
                    seg = cb._patrol_droga(tuple(poz[:3]), {"x": p[0], "y": p[1], "z": p[2]}, uz)
                except bot.Zatrzymano:
                    raise
                except Exception as ex:
                    self.log(f"Wypad: dojście: błąd drogi do {tuple(p)}: {ex!r}")
                    continue
                if not seg:
                    continue
                klucz = (len(seg), -ei)
                if najl is None or klucz < najl[0]:
                    najl = (klucz, [tuple(q) for q in seg], (ei, pi), list(uz))
        return None if najl is None else (najl[1], najl[2], najl[3])

    def _dojscie_start(self, poz, teraz, powod, tylko_gdy_odciety=False):
        """Planuje dojście do planu. True = dojście ruszyło (obieg zużyty przez kolejne wołania _dojscie_krok).
        tylko_gdy_odciety: start wyprawy - dojście tylko gdy żaden z najbliższych punktów planu nie jest osiągalny
        po tym piętrze (połączona postać chodzi po staremu). False = wyłączone / brak drogi: stara ścieżka."""
        if not self._dojscie_wlaczone() or self.etapy is None:
            return False
        if self.dojscie_plany >= DOJSCIE_PLANY_MAX:
            return False
        if self.dojscie_t0 is not None and teraz - self.dojscie_t0 > DOJSCIE_MAX_S:
            return False
        if tylko_gdy_odciety:
            try:
                if self._najblizszy_osiagalny(poz, -1) is not None:
                    return False
            except bot.Zatrzymano:
                raise
            except Exception:
                return False
        plan = self._dojscie_plan(poz)
        if plan is None:
            self._blad("dojscie_brak_drogi", poz=list(poz), powod=powod)
            self.log(f"Wypad: dojście do planu ({powod}) z {tuple(poz)}: brak drogi patrolu")
            return False
        seg, cel, uz = plan
        if powod != "zejscie_z_drogi":          # zejście z drogi (walka, ucieczka) wolno planować wielokrotnie: limit czasu
            self.dojscie_plany += 1
        if self.dojscie_t0 is None:
            self.dojscie_t0 = teraz
        pkt = self.etapy[cel[0]]["punkty"][cel[1]]
        self.dojscie = {"seg": seg, "idx": 0, "seg_xy": set(seg) | {tuple(poz[:3])}, "cel": cel, "pkt": tuple(pkt), "przejscia": uz,
                        "replan": teraz, "powod": powod,
                        "do": teraz + DOJSCIE_LIMIT_S[0] + DOJSCIE_LIMIT_S[1] * len(seg) + DOJSCIE_PRZEJSCIE_S * len(uz)}
        self.postep = None
        self.utk = 0
        self.przystanek_od = None
        self.cb._wypad_reset_klik()
        self.log(f"Wypad: dojście do planu ({powod}) z {tuple(poz)} do etapu {cel[0]} punkt {cel[1]} {tuple(pkt)}, "
                 f"droga {len(seg)} pól" + (f", przez {','.join(uz)}" if uz else ""))
        self._tele("wypad_krok", rodzaj="dojscie_start", powod=powod, poz=list(poz), etap=cel[0], punkt=cel[1],
                   droga=len(seg), przejscia=list(uz))
        return True

    def _dojscie_porazka(self, poz, teraz, opis, blokuj=False):
        """Nieudane dojście: ponowny plan (inne przejście), a gdy się nie da - istniejąca eskalacja (awaria/alarm)."""
        d = self.dojscie
        self.dojscie = None
        self._blad("dojscie_nieudane", poz=list(poz), opis=opis, plan=d["cel"] if d else None)
        if blokuj and d:
            try:
                self.cb._patrol_blokuj_przejscie({"przejscia": d["przejscia"]}, poz, teraz)
            except Exception:
                pass
        if self._dojscie_start(poz, teraz, "ponowne"):
            return True
        return self._awaria("dojscie_trasy", f"dojście do planu z {tuple(poz)} nie wyszło ({opis})")

    def _dojscie_koniec(self, poz, teraz):
        d = self.dojscie
        self.dojscie = None
        self.ei, self.pi = d["cel"]
        self.postep = None
        self.utk = 0
        self.osiag_przesiadki = 0
        self.osiag_proba = float("-inf")
        self.przystanek_od = None
        self.cb._wypad_reset_klik()
        self.log(f"Wypad: dojście do planu zakończone w {tuple(poz)}, etap {self.ei} punkt {self.pi}")
        self._tele("wypad_krok", rodzaj="dojscie_koniec", poz=list(poz), etap=self.ei, punkt=self.pi,
                   czas_s=round(teraz - (self.dojscie_t0 or teraz)))
        return True

    def _dojscie_krok(self, poz, teraz):
        """Jeden obieg dojścia: ten sam marsz co patrol (Cavebot._idz_segment po drodze z grafu przejść)."""
        cb = self.cb
        d = self.dojscie
        pkt = d["pkt"]
        if poz[2] == pkt[2] and cheb(poz, pkt) <= 1:
            return self._dojscie_koniec(poz, teraz)
        if teraz > d["do"] or (self.dojscie_t0 is not None and teraz - self.dojscie_t0 > DOJSCIE_MAX_S):
            self.dojscie_plany = DOJSCIE_PLANY_MAX          # limit czasu: bez ponownych planów, od razu eskalacja
            return self._dojscie_porazka(poz, teraz, "limit czasu", blokuj=True)
        if tuple(poz[:3]) not in d["seg_xy"]:
            if teraz - d["replan"] < 1.0:
                cb.pauza(0.1, 0.3)
                return True
            self.dojscie = None                              # zeszliśmy z drogi (walka, ucieczka): nowy plan z bieżącej pozycji
            if self._dojscie_start(poz, teraz, "zejscie_z_drogi"):
                return True
            return self._awaria("dojscie_trasy", f"dojście do planu: zgubiona droga w {tuple(poz)}")
        with self._dojscie_ctx():
            wynik, d["idx"] = cb._idz_segment(d["seg"], d["idx"])
        try:
            cb.stan = "WYPAD"
        except Exception:
            pass
        if cb.__dict__.pop("pietra_zawrot_seg", False):
            return self._dojscie_porazka(poz, teraz, "przejście pięter nieudane", blokuj=True)
        if wynik is False:
            return self._dojscie_porazka(poz, teraz, "odcinek nieosiągalny", blokuj=True)
        return True

    def _utkniecie(self, poz, e, teraz, wymus=False):
        cb = self.cb
        self.postep = None
        self.utk += 1
        self._blad("utkniecie", poz=list(poz), etap=self.ei, n=self.utk)
        cb._wypad_reset_klik()
        cb.sciany.clear()
        cb.zablokowane.clear()
        if self.utk == 1:
            self.pi = min(self.pi + 2, len(e["punkty"]) - 1)    # przeskocz kilka punktów (obejście przeszkody)
            cb.pauza(1.0, 2.0)
            return True
        if self.utk == 2:
            cb.pauza(5.0, 8.0)                                   # blokada może zejść (gracz/NPC/stwór)
            self.pi = 0 if self.pi > 3 else self.pi
            return True
        self.utk = 0
        return self._awaria("utkniecie", f"brak postępu na etapie {self.ei} w {tuple(poz)}")

    def _etap_gotowy(self, e, poz, teraz):
        cb = self.cb
        self.przystanek_od = None
        self.utk = 0
        self.postep = None
        cb._wypad_reset_klik()
        self._tele("wypad_krok", rodzaj="etap", faza=self.faza, etap=self.ei, poz=list(poz))
        if self.ei + 1 >= len(self.etapy):
            if self.faza == "do":
                self.faza = "sklep"
                self.sklep = None
                self.log(f"Wypad: jestem w sklepie {tuple(poz)}")
                self._tele("wypad_krok", rodzaj="sklep_dojscie", poz=list(poz), czas_s=round(teraz - self.t_start))
            else:
                return self._koniec("ok" if self._sukces() else "bez_zakupow", "")
            return True
        self.ei += 1
        self.pi = 0
        cb.pauza(0.1, 0.3)
        return True

    def _sukces(self):
        return self.wynik != "porazka_sklepu"

    # --- przejścia pięter ---

    def _po_przejsciu(self, e, poz_przed, teraz, rodzaj):
        cb = self.cb
        for _ in range(5):
            cb.spij(0.4)
            p = cb.postac.pozycja()
            if p[2] == e["ladunek"][2]:
                self.log(f"Wypad: {rodzaj} z{poz_przed[2]} -> z{p[2]} w {p}")
                self._tele("wypad_krok", rodzaj=rodzaj, z_od=poz_przed[2], z_do=p[2], poz=list(p))
                cb._wypad_reset_klik()
                self.ei = min(self.ei + 1, len(self.etapy) - 1)
                self.pi = 0
                e["proby"] = 0
                self.utk = 0
                self.postep = None
                self.przystanek_od = None
                return True
        return False

    def _nie_czas(self, e, teraz):
        return teraz < e.get("nast", float("-inf"))

    def _porazka_przejscia(self, e, teraz, typ, limit=None, **d):
        n = e.get("proby", 0)
        e["nast"] = teraz + PRZEJSCIE_ODSTEP[min(n - 1, len(PRZEJSCIE_ODSTEP) - 1)]
        self._blad(typ, proba=n, **d)
        if n >= (limit or ETAP_PRZEJSCIE_PROB):
            e["proby"] = 0
            return self._awaria(typ, f"{n} nieudanych prób przejścia {e['stoi']} -> {e['ladunek']}", e)
        return True

    def _pilnuj_przejscia(self, poz, e, teraz):
        """Bezpiecznik widoczny (19.10): etap przejścia (LINA/DZIURA), w którym pozycja się nie zmienia i nie ma nowej próby
        przez WYPAD_ETAP_MAX_S, kończy się awarią z logiem i powiadomieniem, zamiast kręcić się w ciszy (stoi za daleko ->
        cofnięcie do IDZ -> "na miejscu" -> znów przejście...). Czekanie między próbami (`nast`) nie liczy się do limitu.
        None: w porządku; inaczej wynik obiegu (awaria)."""
        if self._nie_czas(e, teraz):
            self.pj = None
            return None
        klucz = (self.ei, tuple(poz), self.pj_proby)
        if self.pj is None or self.pj[0] != klucz:
            self.pj = [klucz, teraz]
            return None
        limit = float(self._k("WYPAD_ETAP_MAX_S", WYPAD_ETAP_MAX_S))
        if teraz - self.pj[1] <= limit:
            return None
        self.pj = None
        opis = f"przejście {e['typ']} {e['stoi']} -> {e['ladunek']}: brak próby i ruchu od {limit:.0f} s, poz {tuple(poz)}"
        self.log(f"Wypad: {opis}; awaria")
        self._powiadom("Wypad: przejście bez postępu", f"{opis}.", "critical", "wypad_przejscie")
        e["proby"] = 0
        return self._awaria("przejscie_bez_postepu", opis, e)

    def _zajete_pola(self, poz):
        """Pola (x, y) zajęte przez inne postacie/potwory na piętrze `poz` (bez nas)."""
        cb = self.cb
        try:
            f = getattr(cb, "zajete_bez_nas", None)
            if callable(f):
                return {(int(p[0]), int(p[1])) for p in f(tuple(poz))}
            return {(int(m["x"]), int(m["y"])) for m in (getattr(cb, "ostatnie_stwory", None) or ())
                    if m.get("z") == poz[2] and m.get("hp", 100) > 0 and (m["x"], m["y"]) != tuple(poz[:2])}
        except Exception:
            return set()

    def _dziura_sasiednie(self, poz, e):
        """Pola z flagą mapy "zmiana piętra" (flaga 2) w promieniu 1 od pola stania, inne niż zaplanowana dziura:
        plan zakłada dziurę na (x, y) lądowania, a rampa/schody w dół leżą o pole wyżej (19.10: lądowanie y=31813, rampa y=31812).
        -> (wolne, zajete): wolne = posortowane (proste przed skosem, bliżej planowanej dziury), zajete = pola z flagą, na których
        stoi ktoś (nie wchodzimy)."""
        mapa = getattr(self.cb, "mapa", None)
        if mapa is None or not self._k("WYPAD_DZIURA_SASIEDNIE", 1):
            return [], []
        h = e["dziura"]
        zaj = self._zajete_pola(poz)
        wolne, zajete = [], []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (dx, dy) == (0, 0):
                    continue
                q = (poz[0] + dx, poz[1] + dy, poz[2])
                if (q[0], q[1]) == (h[0], h[1]):
                    continue
                try:
                    if not (mapa.flagi(*q) & 2) or mapa.przechodnie(*q) is False:
                        continue
                except Exception:
                    continue
                osiagalne = (q[0], q[1]) not in zaj
                if osiagalne and dx and dy:         # po skosie dojdziemy tylko przez wolne pole pośrednie
                    osiagalne = (poz[0] + dx, poz[1]) not in zaj or (poz[0], poz[1] + dy) not in zaj
                (wolne if osiagalne else zajete).append(q)
        wolne.sort(key=lambda q: (q[0] != poz[0] and q[1] != poz[1], cheb(q, h), q[1], q[0]))
        return wolne, zajete

    def _kier_do_pola(self, poz, q):
        """Kierunek strzałki do sąsiedniego pola q; po skosie najpierw w poziomie, a gdy to pole zajęte, w pionie."""
        dx, dy = q[0] - poz[0], q[1] - poz[1]
        if dx and dy:
            zaj = self._zajete_pola(poz)
            if (poz[0] + dx, poz[1]) in zaj and (poz[0], poz[1] + dy) not in zaj:
                return "Down" if dy > 0 else "Up"
        return ("Right" if dx > 0 else "Left") if dx else ("Down" if dy > 0 else "Up")

    @staticmethod
    def _proby_drabiny(poz, cel):
        """Kolejność prób wejścia (Ctrl+klik = Use): drabina (1 próba), lina z plecaka (2x), drabina, pole własne (0,0), potem sąsiednie
        E / W / N (bez dubla pola drabiny). 17.10: minimapa nie odróżnia liny od drabiny (oba pola żółte), a lina na tej trasie
        zawsze była ostatnia (7. próba, ok. 40-60 s zmarnowane na każdej linie), więc po jednej próbie drabiny od razu lina."""
        pola = [("drabina", cel), ("lina", cel), ("lina", cel), ("drabina", cel), ("wlasne", (poz[0], poz[1], poz[2]))]
        for nazwa, (dx, dy) in (("E", (1, 0)), ("W", (-1, 0)), ("N", (0, -1))):
            q = (poz[0] + dx, poz[1] + dy, poz[2])
            if (q[0], q[1]) != (cel[0], cel[1]):
                pola.append((nazwa, q))
        return pola

    def _lina(self, poz, e, teraz):
        """Przejście w górę: DRABINA (Ctrl+klik na polu drabiny obok pola stania), a po wyczerpaniu prób lina."""
        cb = self.cb
        w = self._pilnuj_przejscia(poz, e, teraz)
        if w is not None:
            return w
        if cheb(poz, e["cel"]) > 1 or poz[2] != e["stoi"][2]:
            # za daleko od pola drabiny: wracamy do chodzenia po poprzednim etapie
            if self.ei > 0 and self.etapy[self.ei - 1]["typ"] == "IDZ":
                self.ei -= 1
                # 14.10: ostatni punkt odcinka (przy przejściu), nie pierwszy: pi = 0 cofało postać do miasta
                self.pi = max(0, len(self.etapy[self.ei].get("punkty") or ()) - 1)
            else:
                return self._awaria("lina_daleko", f"poz {poz}, drabina {e['cel']}")
            return True
        if self._nie_czas(e, teraz):
            cb.pauza(0.2, 0.5)
            return True
        n = e.get("proby", 0)
        proby = self._proby_drabiny(poz, e["cel"])
        e["proby"] = n + 1
        self.pj_proby += 1
        tryb, pole = proby[min(n, len(proby) - 1)]
        rodzaj = "lina" if tryb == "lina" else "drabina"
        self.log(f"Wypad: {rodzaj} próba {n + 1}/{len(proby)} ({tryb}) z {tuple(poz)}, pole {pole[:2]}")
        try:
            if tryb == "lina":
                self.ops.uzyj_line(e["cel"], poz)
            else:
                self.ops.uzyj_pole(pole, poz)
        except bot.Zatrzymano:
            raise
        except BrakEkranu as ex:
            return self._porazka_przejscia(e, teraz, f"{rodzaj}_ekran", limit=len(proby), powod=str(ex), tryb=tryb)
        except Exception as ex:
            return self._porazka_przejscia(e, teraz, f"{rodzaj}_wyjatek", limit=len(proby), powod=repr(ex), tryb=tryb)
        if self._po_przejsciu(e, poz, teraz, rodzaj):
            return True
        return self._porazka_przejscia(e, teraz, f"{rodzaj}_bez_zmiany_pietra", limit=len(proby), tryb=tryb)

    def _dziura(self, poz, e, teraz):
        cb = self.cb
        h = e["dziura"]
        if poz[2] != e["stoi"][2]:
            return True
        w = self._pilnuj_przejscia(poz, e, teraz)
        if w is not None:
            return w
        na_dziurze = (poz[0], poz[1]) == (h[0], h[1])
        # 19.10: plan zakłada dziurę na (x, y) lądowania, a rampa w dół leży o pole wyżej (flaga 2 na sąsiednim polu).
        # Sąsiednie pola z flagą zmiany piętra (promień 1 od nas), wolne od graczy, próbujemy po planowanym polu.
        sasiednie, zajete_flaga = ([], [])
        if not na_dziurze:
            sasiednie, zajete_flaga = self._dziura_sasiednie(poz, e)
        if cheb(poz, h) > 1:
            if sasiednie:
                pass                    # planowana dziura za daleko, ale obok nas jest rampa: próbujemy ją
            elif zajete_flaga:
                klucz_ostrz = ("dziura_zajeta", self.ei, tuple(poz))
                if klucz_ostrz not in self.ostrzezenia:
                    self.ostrzezenia.add(klucz_ostrz)
                    self.log(f"Wypad: dziura {tuple(h)[:2]}: pola ze zmianą piętra obok {tuple(poz)[:2]} zajęte "
                             f"({[q[:2] for q in zajete_flaga]}), czekam")
                cb.pauza(0.5, 1.0)       # bezpiecznik _pilnuj_przejscia kończy to awarią, gdy nikt nie zejdzie
                return True
            elif self.ei > 0 and self.etapy[self.ei - 1]["typ"] == "IDZ":
                self.ei -= 1
                # 14.10: ostatni punkt odcinka (przy przejściu), nie pierwszy: pi = 0 cofało postać do miasta
                self.pi = max(0, len(self.etapy[self.ei].get("punkty") or ()) - 1)
                return True
            else:
                return self._awaria("dziura_daleko", f"poz {poz}, dziura {h}")
        if self._nie_czas(e, teraz):
            cb.pauza(0.2, 0.5)
            return True
        n = e.get("proby", 0)
        e["proby"] = n + 1
        self.pj_proby += 1
        # kolejność prób: pewna dziura = krok; niepewna (kratka/właz bez flagi) = Use, krok, Use na własnym polu
        tryby = ("krok", "lopata", "krok", "use", "lopata", "krok") if e["pewna"] else \
            ("use", "krok", "use_wlasne", "lopata", "krok", "use")
        if cheb(poz, h) > 1:
            lista = [("krok", q) for q in sasiednie]
        elif e["pewna"] or not sasiednie:
            lista = [(t, h) for t in tryby]
        else:
            # planowane pole (2 pierwsze próby), potem sąsiednie pola z flagą mapy, potem reszta prób na planowanym
            lista = [(t, h) for t in tryby[:2]] + [("krok", q) for q in sasiednie] + [(t, h) for t in tryby[2:]]
        limit = max(ETAP_PRZEJSCIE_PROB, len(lista)) if cheb(poz, h) <= 1 else ETAP_PRZEJSCIE_PROB
        tryb, cel_p = lista[n % len(lista)]
        if tryb == "krok" and na_dziurze:
            tryb = "use_wlasne"
        if cel_p != h or sasiednie:
            self.log(f"Wypad: dziura próba {n + 1}/{limit} ({tryb}) z {tuple(poz)}, pole {tuple(cel_p)[:2]}"
                     f"{' (sąsiednie z flagą mapy, plan: ' + str(tuple(h)[:2]) + ')' if cel_p != h else ''}")
        try:
            if tryb == "krok":
                # strzałki nie chodzą po skosie: z pola po skosie najpierw w poziomie (potem dziura jest obok)
                kier = self._kier_do_pola(poz, cel_p)
                cb.postac.krok(kier)
            elif tryb == "lopata":
                uzyj = getattr(self.ops, "uzyj_lopate", None)
                if not self._k("PIETRA_LOPATA", 1) or uzyj is None:
                    cb.pauza(0.2, 0.5)
                    return True
                if self._k("PIETRA_LOPATA_TYLKO_Z7", 1) and poz[2] != 7:
                    cb.pauza(0.2, 0.5)          # 14.10: schody/dziury w jaskini nie są zasypane, łopata tylko na z7 (jak w pietra.py)
                    return True
                cel_k = (poz[0], poz[1], poz[2]) if na_dziurze else h
                self.log(f"Wypad: dziura {tuple(h)[:2]} zasypana? próba {n + 1}: odkopuję łopatą ({cel_k[:2]}) z {tuple(poz)}")
                self._tele("wypad_krok", rodzaj="lopata", poz=list(poz), pole=list(cel_k), proba=n + 1)
                uzyj(cel_k, poz)
                cb.spij(0.6)
            elif tryb == "use":
                self.ops.uzyj_pole(h, poz)
            else:
                self.ops.uzyj_pole((poz[0], poz[1], poz[2]), poz)
        except bot.Zatrzymano:
            raise
        except BrakEkranu as ex:
            return self._porazka_przejscia(e, teraz, "dziura_ekran", limit=limit, powod=str(ex), tryb=tryb)
        except Exception as ex:
            return self._porazka_przejscia(e, teraz, "dziura_wyjatek", limit=limit, powod=repr(ex), tryb=tryb)
        if self._po_przejsciu(e, poz, teraz, "dziura"):
            return True
        return self._porazka_przejscia(e, teraz, "dziura_bez_zmiany_pietra", limit=limit, tryb=tryb)

    # --- drzwi ---

    @staticmethod
    def _za_drzwiami(poz, e):
        """Stoimy na kafelku drzwi albo na polu naprzeciw pola `stoi` (po drugiej stronie drzwi)."""
        h, st = e["drzwi"], e["stoi"]
        if poz[2] != h[2]:
            return False
        if (poz[0], poz[1]) == (h[0], h[1]):
            return True
        return cheb(poz, h) == 1 and cheb(poz, st) >= 2

    def _drzwi_przeszlismy(self, e, poz, teraz):
        h = e["drzwi"]
        self.log(f"Wypad: drzwi {h[:2]} otwarte, jestem w {tuple(poz)}")
        self._tele("wypad_krok", rodzaj="drzwi", drzwi=list(h), poz=list(poz), proba=e.get("proby", 0))
        self.drzwi_otwarte.add(tuple(h))
        self.cb._wypad_reset_klik()
        self.ei = min(self.ei + 1, len(self.etapy) - 1)
        self.pi = 0
        e["proby"] = 0
        e["daleko"] = 0
        e["nast"] = float("-inf")
        self.utk = 0
        self.postep = None
        self.przystanek_od = None
        return True

    def _porazka_drzwi(self, e, teraz, typ, **d):
        n = e.get("proby", 0)
        e["nast"] = teraz + DRZWI_ODSTEP[min(max(n, 1) - 1, len(DRZWI_ODSTEP) - 1)]
        self._blad(typ, proba=n, drzwi=list(e["drzwi"]), **d)
        if n >= DRZWI_PROB:
            e["proby"] = 0
            self.drzwi_otwarte.discard(tuple(e["drzwi"]))
            return self._awaria(typ, f"{n} nieudanych prób otwarcia drzwi {e['drzwi']} z {e['stoi']}", e)
        return True

    def _drzwi(self, poz, e, teraz):
        """Zamknięte drzwi: Use na kafelku drzwi z pola obok, ~0,6-1 s czekania, krok na kafelek; udane = pozycja
        na kafelku drzwi albo za nimi. Do DRZWI_PROB prób (Use / sam krok na zmianę), potem _awaria."""
        cb = self.cb
        h, st = e["drzwi"], e["stoi"]
        if poz[2] != st[2]:
            return True
        if self._za_drzwiami(poz, e):
            return self._drzwi_przeszlismy(e, poz, teraz)
        if cheb(poz, h) > 1:
            e["daleko"] = e.get("daleko", 0) + 1
            if e["daleko"] >= DRZWI_DALEKO_MAX:
                e["daleko"] = 0
                return self._awaria("drzwi_daleko", f"poz {poz}, drzwi {h}", e)
            if self.ei > 0 and self.etapy[self.ei - 1]["typ"] == "IDZ":
                self.ei -= 1
                # 14.10: ostatni punkt odcinka (przy przejściu), nie pierwszy: pi = 0 cofało postać do miasta
                self.pi = max(0, len(self.etapy[self.ei].get("punkty") or ()) - 1)
                return True
            return self._awaria("drzwi_daleko", f"poz {poz}, drzwi {h}", e)
        if self._nie_czas(e, teraz):
            cb.pauza(0.2, 0.5)
            return True
        n = e.get("proby", 0)
        e["proby"] = n + 1
        # drzwi, które już otwieraliśmy, bywają otwarte (powrót): najpierw sam krok; inaczej Use
        tryby = ("krok", "use", "krok") if tuple(h) in self.drzwi_otwarte else ("use", "krok", "use")
        tryb = tryby[n % len(tryby)]
        self.log(f"Wypad: drzwi {h[:2]} próba {n + 1}/{DRZWI_PROB} ({tryb}) z {tuple(poz)}")
        try:
            if tryb == "use":
                self.ops.uzyj_pole(h, poz)
                cb.spij(random.uniform(*DRZWI_CZEKAJ_S))
            dx, dy = h[0] - poz[0], h[1] - poz[1]
            # strzałki nie chodzą po skosie: najpierw w poziomie
            kier = ("Right" if dx > 0 else "Left") if dx else ("Down" if dy > 0 else "Up")
            cb.postac.krok(kier)
        except bot.Zatrzymano:
            raise
        except BrakEkranu as ex:
            return self._porazka_drzwi(e, teraz, "drzwi_ekran", powod=str(ex), tryb=tryb)
        except Exception as ex:
            return self._porazka_drzwi(e, teraz, "drzwi_wyjatek", powod=repr(ex), tryb=tryb)
        for _ in range(3):
            p = cb.postac.pozycja()
            if self._za_drzwiami(p, e):
                return self._drzwi_przeszlismy(e, p, teraz)
            cb.spij(0.3)
        return self._porazka_drzwi(e, teraz, "drzwi_bez_wejscia", tryb=tryb)

    # --- sklep ---

    def _npc_wiadomosci(self, nowe):
        """Odpowiedzi NPC z listy nowych wiadomości (autor = NPC; gdy autor pusty - wszystkie nie nasze)."""
        wynik = []
        for w in nowe:
            autor = (w.get("autor") or "").strip()
            if autor.casefold() == self.npc.casefold():
                wynik.append(w["tekst"])
            elif not autor and not re.match(r"^(you|your)\b", w["tekst"], re.I):
                wynik.append(w["tekst"])
        return wynik

    def _sklep(self, poz, teraz):
        cb = self.cb
        s = self.sklep
        if s is None:
            lista = self.zakupy()
            plecak = self.ops.plecak()
            s = self.sklep = {"lista": lista, "i": 0, "krok": "hi", "od": teraz, "nast": teraz,
                              "hi_proby": 0, "proby_przedmiotu": 0, "plecak0": plecak, "wynik": {},
                              "odpowiedzi": [], "t0": teraz, "rozmowa": False, "pomin": 0}
            if getattr(cb, "wypad_czat", None) is not None:
                try:
                    cb.wypad_czat.npc.add(self.npc)         # mózg nie ma traktować Al Dee jak gracza
                except Exception:
                    pass
        if s["i"] >= len(s["lista"]):
            return self._koniec_sklepu(teraz)
        # odpowiedzi NPC
        try:
            nowe = self.ops.wiadomosci()
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            nowe = []
            self._blad("wiadomosci", opis=repr(ex))
        odp = self._npc_wiadomosci(nowe)
        for t in odp:
            s["odpowiedzi"].append(t)
            self.log(f"Wypad: NPC: {t!r}")
        klucz, cel = s["lista"][s["i"]]
        slowo = self._slowo(klucz)
        krok = s["krok"]
        if teraz < s["nast"]:
            cb.pauza(0.2, 0.5)
            return True
        # ile brakuje do celu (świeży odczyt przed "buy")
        if krok == "hi":
            if not s["rozmowa"]:
                self._powiedz("hi")
                s["hi_proby"] += 1
                s["od"] = teraz
                s["krok"] = "hi_czeka"
                s["odpowiedzi"] = []
            else:
                s["krok"] = "buy"
            cb.pauza(0.3, 0.7)
            return True
        if krok == "hi_czeka":
            if any(ODP_POWITANIE.search(t) or ODP_PYTANIE.search(t) for t in odp) or \
                    any(ODP_POWITANIE.search(t) for t in s["odpowiedzi"]):
                s["rozmowa"] = True
                s["krok"] = "buy"
            elif teraz - s["od"] > ODP_NPC_S:
                if s["hi_proby"] >= NPC_PROBY:
                    self._blad("brak_npc", proby=s["hi_proby"])
                    s["lista"] = []                  # sklep nieosiągalny: wracamy
                    self.wynik = "porazka_sklepu"
                    return self._koniec_sklepu(teraz)
                self._blad("brak_odpowiedzi_npc", proba=s["hi_proby"])
                s["nast"] = teraz + SKLEP_PAUZA_NPC_S
                s["krok"] = "hi"
            cb.pauza(0.2, 0.5)
            return True
        if krok == "buy":
            plecak = self.ops.plecak()
            ma = self._ile(plecak, klucz)
            s["ma_przed"] = ma
            s["ids_przed"] = dict((plecak or {}).get("id", {}))
            if ma is not None and ma >= cel:
                self.log(f"Wypad: {klucz}: mam {ma} >= {cel}, pomijam")
                s["wynik"][klucz] = "mam"
                return self._nastepny_przedmiot(s, teraz)
            ile = self._ile_zakupu(s, klucz, cel, ma)      # hak (domyślnie cel - ma); wyprawa.py: cap, złoto, koszt
            if ile <= 0:
                self.log(f"Wypad: {klucz}: nie kupuję (limit cap/złoto/koszt), mam {ma}")
                s["wynik"][klucz] = s["wynik"].get(klucz) or "brak_miejsca"
                return self._nastepny_przedmiot(s, teraz)
            s["ile"] = ile
            self._powiedz(f"buy {ile} {slowo}")
            s["od"] = teraz
            s["krok"] = "buy_czeka"
            s["odpowiedzi"] = []
            cb.pauza(0.3, 0.7)
            return True
        if krok == "buy_czeka":
            if any(ODP_PYTANIE.search(t) for t in s["odpowiedzi"]):
                kontrola = self._kontrola_oferty(s, klucz, teraz)     # hak: None = bierzemy ofertę
                if kontrola is None:
                    s["krok"] = "yes"
                elif kontrola[0] == "zmniejsz":
                    self._powiedz("no")
                    s["limit_ile"] = kontrola[1]
                    s["krok"] = "buy"
                    s["nast"] = teraz + 1.2
                    s["odpowiedzi"] = []
                else:
                    self._powiedz("no")
                    return self._odmowa(s, klucz, kontrola[1], teraz)
            elif any(ODP_BRAK_MIEJSCA.search(t) for t in s["odpowiedzi"]):
                return self._odmowa(s, klucz, "brak_miejsca", teraz)
            elif any(ODP_BRAK_ZLOTA.search(t) for t in s["odpowiedzi"]):
                return self._odmowa(s, klucz, "brak_zlota", teraz)
            elif any(ODP_ODMOWA.search(t) for t in s["odpowiedzi"]):
                return self._odmowa(s, klucz, "odmowa: " + s["odpowiedzi"][-1][:80], teraz)
            elif teraz - s["od"] > ODP_NPC_S:
                if s["proby_przedmiotu"] < 1:
                    s["proby_przedmiotu"] += 1
                    s["rozmowa"] = False          # może rozmowa wygasła: "hi" jeszcze raz
                    s["hi_proby"] = 0
                    s["krok"] = "hi"
                else:
                    return self._odmowa(s, klucz, "brak_odpowiedzi", teraz)
            cb.pauza(0.2, 0.5)
            return True
        if krok == "yes":
            self._powiedz("yes")
            s["od"] = teraz
            s["krok"] = "weryfikacja"
            cb.pauza(0.3, 0.7)
            return True
        if krok == "weryfikacja":
            plecak = self.ops.plecak()
            ma = self._ile(plecak, klucz)
            przed = s.get("ma_przed") or 0
            nowe_id = {}
            if plecak is not None:
                przed_ids = s.get("ids_przed", {})
                nowe_id = {i: n - przed_ids.get(i, 0) for i, n in plecak.get("id", {}).items()
                           if n > przed_ids.get(i, 0)}
            if (ma is not None and ma > przed) or nowe_id:
                kupiono = (ma - przed) if (ma is not None and ma > przed) else sum(nowe_id.values())
                self.kupione[klucz] = kupiono + self.kupione.get(klucz, 0)
                s["wynik"][klucz] = "kupione"
                self.log(f"Wypad: kupione {klucz}: +{kupiono} ({przed} -> {ma}); nowe ID {nowe_id}")
                self._tele("wypad_krok", rodzaj="zakup", przedmiot=klucz, przed=przed, po=ma, nowe_id=nowe_id)
                self._po_zakupie(s, klucz, kupiono)
                return self._nastepny_przedmiot(s, teraz)
            if any(ODP_BRAK_MIEJSCA.search(t) for t in s["odpowiedzi"]):
                return self._odmowa(s, klucz, "brak_miejsca", teraz)
            if any(ODP_BRAK_ZLOTA.search(t) for t in s["odpowiedzi"]):
                return self._odmowa(s, klucz, "brak_zlota", teraz)
            if teraz - s["od"] > WERYF_S:
                self._blad("zakup_bez_wzrostu", przedmiot=klucz, przed=przed, po=ma)
                if s["proby_przedmiotu"] < 1:
                    s["proby_przedmiotu"] += 1
                    s["krok"] = "buy"
                    return True
                return self._odmowa(s, klucz, "brak_wzrostu", teraz)
            s["nast"] = teraz + 1.2
            return True
        return True

    # --- haki dla wyprawa.py (domyślnie zachowanie wypadu po pochodnie bez zmian) ---

    def _slowo(self, klucz):
        return NAZWY_PRZEDMIOTOW.get(klucz, klucz)

    def _ile_zakupu(self, s, klucz, cel, ma):
        """Ile sztuk powiedzieć w "buy N ..." (<= 0 = pomiń przedmiot)."""
        ile = cel - (ma or 0)
        lim = s.get("limit_ile")
        return min(ile, lim) if lim is not None else ile

    def _kontrola_oferty(self, s, klucz, teraz):
        """Po pytaniu NPC "Do you want to buy N ... for X gold?": None = "yes"; ("zmniejsz", n) = "no" i nowe buy n;
        ("odmowa", powod) = "no" i rezygnacja z przedmiotu."""
        return None

    def _po_zakupie(self, s, klucz, kupiono):
        """Po potwierdzonym zakupie (wzrost liczby sztuk w plecaku)."""

    def _max_czas(self):
        return MAX_CZAS_S

    def _powiedz(self, tekst):
        self.log(f"Wypad: mówię {tekst!r}")
        self.ops.czat(tekst)

    def _odmowa(self, s, klucz, powod, teraz):
        self.log(f"Wypad: nie kupiłem {klucz}: {powod}")
        self._tele("wypad_zakup_odmowa", przedmiot=klucz, powod=powod, odpowiedzi=s["odpowiedzi"][-3:])
        s["wynik"][klucz] = "odmowa"
        if powod == "brak_zlota":
            s["lista"] = s["lista"][:s["i"] + 1]     # bez złota nie próbujemy kolejnych przedmiotów
        return self._nastepny_przedmiot(s, teraz)

    def _nastepny_przedmiot(self, s, teraz):
        s["i"] += 1
        s["krok"] = "hi"
        s.pop("limit_ile", None)
        s.pop("zmniejszen", None)
        s["proby_przedmiotu"] = 0
        s["hi_proby"] = 0
        s["nast"] = teraz + 0.5
        return True

    def _koniec_sklepu(self, teraz):
        s = self.sklep
        wynik = s["wynik"] if s else {}
        torch_ok = wynik.get("torch") in ("kupione", "mam")
        potrzebne = [k for k, _ in (s["lista"] if s else [])]
        if self.wynik != "porazka_sklepu":
            self.wynik = "ok" if (torch_ok or any(v == "kupione" for v in wynik.values())) else "porazka_sklepu"
        self.log(f"Wypad: sklep zakończony: {wynik}, wynik {self.wynik}")
        self._tele("wypad_krok", rodzaj="sklep_koniec", wynik=wynik, kupione=dict(self.kupione),
                   czas_s=round(teraz - self.t_start))
        self.faza = "z"
        self.etapy = self._plan()[1]
        self.sklep = None
        poz = self.cb.postac.pozycja()
        if not self._resync_globalny(poz):
            return self._awaria("zgubiona_pozycja", f"po sklepie poz {poz}")
        self.postep = None
        self.przystanek_od = None
        self.cb._wypad_reset_klik()
        return True

    # --- koniec / awarie ---

    def _awaria(self, typ, opis, etap=None):
        """Nieodwracalny problem w wypadzie. W drodze do sklepu: wracamy (faza "z"); w drodze powrotnej na
        przejściu piętra w mieście: ponawiamy z długim odstępem i powiadomieniem; inaczej koniec."""
        cb = self.cb
        teraz = cb.zegar()
        self.dojscie = None
        self._blad(typ, opis=opis)
        try:   # 19.10 ratunek F1 (S1, cień): nieodwracalny problem wyprawy
            z = getattr(cb, "_ratunek_zdarzenie", None)
            if z is not None:
                z("porazka_trasy", None, co="wyprawa", typ=typ, powod=opis)
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        self.wynik = "porazka_sklepu" if self.faza != "z" else (self.wynik or "awaria")
        if self.faza in ("do", "sklep"):
            self.log(f"Wypad: awaria ({typ}: {opis}), wracam na łowisko bez zakupów")
            self.faza = "z"
            self.sklep = None
            try:
                self.etapy = self._plan()[1]
            except Exception:
                return self._koniec("blad", opis)
            poz = cb.postac.pozycja()
            if not self._resync_globalny(poz):
                return self._koniec("blad", opis)
            self.postep = None
            self.utk = 0
            cb._wypad_reset_klik()
            return True
        # faza "z"
        if etap is not None and etap["typ"] in ("DZIURA", "LINA"):
            if teraz - self.awaria_log > 600:
                self.awaria_log = teraz
                self._powiadom("Wypad: utknąłem w mieście", f"{typ}: {opis}. Bot stoi, potrzebny człowiek.",
                               "critical", "wypad_utknal")
            etap["nast"] = teraz + AWARIA_PO_S
            etap["proby"] = 0
            return True
        return self._koniec("blad", opis)

    def przerwij(self, powod):
        """STOP / ALARM_GM / zewnętrzne przerwanie: koniec wypadu bez wracania na trasę, bez wznowienia."""
        if self.stan == "SPOKOJ" and not powod:
            return
        self.zablokowany = True
        self.dojscie = None
        self.log(f"Wypad: przerwany ({powod}); samoczynnie nie wznowię")
        self._tele("wypad_koniec", wynik="przerwany", powod=powod, kupione=dict(self.kupione),
                   czas_s=round(self.cb.zegar() - self.t_start) if self.t_start else 0)
        self.stan = "SPOKOJ"
        self.faza = None
        self.cb.wypad_aktywny = False

    def _koniec(self, wynik, opis):
        cb = self.cb
        teraz = cb.zegar()
        self.dojscie = None
        if wynik == "ok":
            self.porazki = 0
            self.blokada_do = teraz + PO_SUKCESIE_S
        else:
            self.porazki += 1
            if self.porazki >= MAX_PORAZEK:
                self.blokada_do = teraz + PO_PORAZKACH_S
                self.log(f"Wypad: {self.porazki} nieudane z rzędu, gram po ciemku przez {PO_PORAZKACH_S / 60:.0f} min")
                self._powiadom("Wypad po pochodnie nie wychodzi",
                               f"{self.porazki} nieudane z rzędu ({opis or wynik}). Gram po ciemku, sprawdź.",
                               "critical", "wypad_porazki")
            else:
                self.blokada_do = teraz + PO_PORAZCE_S
                self._powiadom("Wypad nieudany", f"{opis or wynik}; wracam na łowisko", "normal", "wypad_porazka")
        poz = cb.postac.pozycja()
        self.log(f"Wypad: koniec ({wynik}) w {tuple(poz)}, kupione {self.kupione}, "
                 f"{teraz - self.t_start:.0f} s")
        self._tele("wypad_koniec", wynik=wynik, opis=opis, kupione=dict(self.kupione),
                   czas_s=round(teraz - self.t_start), poz=list(poz), porazki=self.porazki)
        self.stan = "SPOKOJ"
        self.faza = self.etapy = None
        self.sklep = None
        self.wynik = None
        cb.wypad_aktywny = False
        cb.ustaw_stan("IDZ", "po wypadzie")
        cb._wypad_wroc_na_trase(poz)
        return True
