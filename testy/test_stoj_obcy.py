"""24.10 STÓJ: obcy gracz blisko = wylogowanie (stoj_obcy.py, cavebot.py `_stoj_obcy_tick`, pokretla.py STOJ_GRACZ_WYLOGUJ_ODL).
Karol 24.10 22:08: „wydra niech robi runy tu, gdzie stoi, a jak ktoś do niej podejdzie z graczy, to niech się wyloguje".
Wyłącznie atrapy: bez gry, bez X11, bez zrzutów ekranu, bez prawdziwych plików instancji, bez uruchamiania pomocnika.
  python3 -I testy/test_stoj_obcy.py"""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, shutil, sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import bot, cavebot, pokretla, stoj, stoj_obcy

CAVELOG = []
cavebot.log = lambda *a: CAVELOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0; cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

TMP = Path(tempfile.mkdtemp(prefix="test_stoj_obcy_"))
POLE = (100, 100, 7)
NPC = "a prisoner"                       # z serwis_akcje.NPC_NAZWY
stoj_obcy.nicki_naszych = lambda katalog_instancji=None: {"wydra", "ela"}    # bez czytania prawdziwych instancje/*/profil.json


class Swiat:
    def __init__(s, poz=POLE, hp=100):
        s.t = 0.0; s.poz = list(poz); s.hp = hp; s.max_hp = 100
        s.stwory = []; s.klawisze = []; s.ataki = []; s.alarmy = []; s.kroki = 0
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": s.max_hp, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(x) for x in s.stwory]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; p.s.kroki += 1
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

def prosta(start, cel, zajete=(), dlugosc=1, skosy=True):
    x, y, z = start; out = []
    while (x, y) != tuple(cel[:2]):
        x += (cel[0] > x) - (cel[0] < x); y += (cel[1] > y) - (cel[1] < y); out.append((x, y, z))
    return out

def mob(x, y, id_=50, nazwa="Rat"):
    return {"id": id_, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": 7, "hp": 100, "bije_nas": False}

def gracz(dx, dy, nazwa="Obcy", id_=70, z=7, **kw):
    d = {"id": id_, "nazwa": nazwa, "gracz": True, "x": POLE[0] + dx, "y": POLE[1] + dy, "z": z, "hp": 100}
    d.update(kw); return d


class Scena:
    """Bot w trybie STÓJ z wstrzykniętymi: Ctrl+L, ekranem, zamknięciem sesji i powiadomieniem."""
    def __init__(sc, nazwa, odl=3, stoj_wl=True, ekran=None):
        sc.k = TMP / nazwa; sc.k.mkdir()
        sc.s = Swiat(); s = sc.s
        sc.ctrl = []; sc.zamkn = []; sc.powiad = []; sc.uh = 0; sc.uh_w_epizodzie = 0
        atak = lambda m_, g: s.ataki.append((m_["id"], s.t))
        loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
        sc.b = b = cavebot.Cavebot(P(s), [POLE, (112, 100, 7)], zapytaj=s.zapytaj, atak=atak, alarm=lambda w: s.alarmy.append(w),
                                   spij=s.spij, zegar=s.zegar, loot=loot)
        b.droga = prosta
        b._alarm_pk = lambda t: s.alarmy.append(t)
        b._pk_powiadom = lambda tytul, tresc, klucz: sc.powiad.append((tytul, tresc, klucz))
        b.stoj_katalog = str(sc.k)
        b.stoj_obcy_ctrl_l = lambda: sc.ctrl.append(s.t)
        b.stoj_obcy_ekran = ekran or (lambda: "gra")
        b.stoj_obcy_zamknij = lambda id_: sc.zamkn.append(id_)
        orig = b._uh_tick
        def uh(*a, **kw):
            sc.uh += 1
            if b.stoj_obcy_ep is not None:
                sc.uh_w_epizodzie += 1
            return orig(*a, **kw)
        b._uh_tick = uh
        cavebot.STOJ_GRACZ_WYLOGUJ_ODL = odl
        if stoj_wl:
            stoj.wlacz(sc.k)
    def tiki(sc, n):
        for _ in range(n):
            if not sc.b.tick():
                return False
        return True


def scenariusz(nazwa, stwory, odl=3, ticks=14, **kw):
    sc = Scena(nazwa, odl=odl, **kw)
    sc.tiki(2)
    sc.s.stwory = stwory
    sc.tiki(ticks)
    return sc


def logout_ok(sc):
    return len(sc.ctrl) >= 1 or (sc.k / "STOP_RECZNY").exists()


# ---------- 1. obcy_gracze: kto jest obcym ----------
nasze = {"wydra", "ela"}; npc = {NPC}
pozy = POLE
def og(lista, odl=3, nick="Wydra"):
    return stoj_obcy.obcy_gracze(lista, pozy, nick, nasze, npc, odl)
sprawdz("1a obcy w 3 polach: wykryty", og([gracz(3, 0)]) == [(3, "Obcy")], og([gracz(3, 0)]))
sprawdz("1b obcy w 4 polach przy N=3: brak", og([gracz(4, 0)]) == [])
sprawdz("1c Czebyszew: (3,3) = 3 pola, (4,1) = 4 pola", og([gracz(3, 3)]) == [(3, "Obcy")] and og([gracz(4, 1)]) == [])
sprawdz("1d N=0: wyłączone", og([gracz(1, 0)], odl=0) == [])
sprawdz("1e inne piętro: brak", og([gracz(1, 0, z=6)]) == [])
sprawdz("1f nasza postać (nick z profil.json, bez względu na wielkość liter): brak", og([gracz(1, 0, "ELA"), gracz(1, 1, "wydra")]) == [])
sprawdz("1g własny nick: brak", og([gracz(0, 0, "Wydra")], nick="Wydra") == [])
sprawdz("1h NPC: brak; NPC z czaszką (PK) już nie jest NPC", og([gracz(1, 0, NPC)]) == [] and og([gracz(1, 0, NPC, czaszka=True)]) != [])
sprawdz("1i potwór (gracz False): brak", og([mob(1, 0)]) == [])
sprawdz("1j widmo i martwy (hp 0): brak", og([gracz(1, 0, widmo=True), gracz(1, 1, "Zmarly", id_=71, hp=0)]) == [])
sprawdz("1k wpis bez współrzędnych / śmieci: bez wyjątku", og([{"gracz": True, "nazwa": "X"}, None, "abc"]) == [])
sprawdz("1l kolejność: najbliższy pierwszy", og([gracz(3, 0, "Daleki"), gracz(1, 1, "Bliski", id_=71)]) == [(1, "Bliski"), (3, "Daleki")])

# ---------- 2. Wykrywacz: 2 odczyty ----------
w = stoj_obcy.Wykrywacz()
sprawdz("2a jeden odczyt: brak potwierdzenia", w.krok(0.0, [(2, "Obcy")]) is None)
sprawdz("2b ten sam skan w 0,2 s (< odstęp): to nie nowy odczyt", w.krok(0.2, [(2, "Obcy")]) is None)
sprawdz("2c drugi odczyt po >= 0,5 s: potwierdzony", w.krok(0.7, [(2, "Obcy")]) == (2, "Obcy"))
w = stoj_obcy.Wykrywacz(); w.krok(0.0, [(2, "Obcy")])
sprawdz("2d pusto między odczytami zeruje licznik", w.krok(1.0, []) is None and w.krok(2.0, [(2, "Obcy")]) is None)
w = stoj_obcy.Wykrywacz(); w.krok(0.0, [(2, "Obcy")])
sprawdz("2e przerwa > 5 s zeruje licznik", w.krok(9.0, [(2, "Obcy")]) is None)
w = stoj_obcy.Wykrywacz(); w.krok(0.0, [(2, "A")])
sprawdz("2f dwa różne nicki po jednym odczycie: brak (ten sam nick w obu)", w.krok(1.0, [(2, "B")]) is None)

# ---------- 3. Epizod: bramka spokoju, PZ-lock, limit ----------
logi = []
ctrl = []; spokojny = [False]; ekran_stan = ["gra"]
ep = stoj_obcy.Epizod(0.0, "Obcy", 2, lambda: ctrl.append(1), lambda: ekran_stan[0], lambda hp: (spokojny[0], "walka" if not spokojny[0] else "spokój", 100),
                      log=logi.append)
sprawdz("3a bez spokoju: niespokojnie, zero klawiszy", ep.krok(0.0) == "niespokojnie" and ep.krok(1.0) == "niespokojnie" and not ctrl)
spokojny[0] = True
sprawdz("3b spokój + ekran gra: Ctrl+L", ep.krok(2.0) == "ctrl_l" and len(ctrl) == 1)
sprawdz("3c następna próba dopiero po 2 s (pierwszy odstęp), potem co 4 s", ep.krok(3.0) == "czeka" and ep.krok(4.1) == "ctrl_l" and len(ctrl) == 2
        and ep.krok(6.0) == "czeka" and ep.krok(8.0) == "czeka" and ep.krok(8.2) == "ctrl_l" and len(ctrl) == 3, ctrl)
ekran_stan[0] = "nieznany"
sprawdz("3d ekran nieznany: żadnego klawisza (Ctrl+L tylko na pewnym ekranie gry)", ep.krok(13.0) == "czeka" and len(ctrl) == 3)
ekran_stan[0] = "enter_game"
sprawdz("3e ekran logowania: wylogowano", ep.krok(14.0) == "wylogowano")
ep = stoj_obcy.Epizod(0.0, "Obcy", 2, lambda: ctrl.append(1), lambda: "zgon", lambda hp: (True, "spokój", 100), log=logi.append)
sprawdz("3f zgon: stop bez klawiszy", ep.krok(0.0) == "zgon")
ep = stoj_obcy.Epizod(0.0, "Obcy", 2, lambda: None, lambda: "gra", lambda hp: (False, "walka", 100), log=logi.append, limit_s=300.0)
sprawdz("3g limit czasu po 300 s niespokoju", ep.krok(100.0) == "niespokojnie" and ep.krok(301.0) == "limit")
n_ctrl = []
ep = stoj_obcy.Epizod(0.0, "Obcy", 2, lambda: n_ctrl.append(1), lambda: "gra", lambda hp: (True, "spokój", 100), log=logi.append, limit_s=60.0)
t = 0.0
while t < 70 and ep.krok(t) != "limit":
    t += 0.5
sprawdz("3h PZ-lock (Ctrl+L bez skutku): ponawia co 4 s i poddaje się po limicie", 13 <= len(n_ctrl) <= 17 and t > 60, (len(n_ctrl), t))

# ---------- 4. cavebot: scenariusze ----------
sc = scenariusz("trzy_pola", [gracz(3, 0)], odl=3, ticks=1)
sprawdz("4a 1 odczyt (jeden obieg z obcym): nic", not sc.ctrl and sc.b.stoj_obcy_ep is None)
sc = Scena("jeden_odczyt"); sc.tiki(2); sc.s.stwory = [gracz(2, 0)]; sc.tiki(1); sc.s.stwory = []; sc.tiki(15)
sprawdz("4b obcy mignął w jednym odczycie i zniknął: nic (bez Ctrl+L, bez STOP)", not sc.ctrl and not (sc.k / "STOP").exists() and sc.b.stoj_obcy_ep is None)

sc = scenariusz("trzy_pola_2", [gracz(3, 0)], odl=3, ticks=20, ekran=None)
sprawdz("4c 3 pola + 2 odczyty: Ctrl+L naciśnięty", len(sc.ctrl) >= 1, (len(sc.ctrl), sc.b.stoj_obcy_ep))
sprawdz("4c' bot nie chodził i nie bił graczy", sc.s.kroki == 0 and not sc.s.ataki, (sc.s.kroki, sc.s.ataki))
sc = scenariusz("cztery_pola", [gracz(4, 0)], odl=3, ticks=25)
sprawdz("4d 4 pola przy N=3: nic", not sc.ctrl and sc.b.stoj_obcy_ep is None and not (sc.k / "STOP").exists())
sc = scenariusz("n_zero", [gracz(1, 0)], odl=0, ticks=25)
sprawdz("4e N=0 (domyślnie): nic", not sc.ctrl and sc.b.stoj_obcy_ep is None and not (sc.k / "STOP").exists())
sc = scenariusz("npc", [gracz(1, 0, NPC)], odl=3, ticks=25)
sprawdz("4f NPC obok: nic", not sc.ctrl and sc.b.stoj_obcy_ep is None)
sc = scenariusz("nasza", [gracz(1, 0, "Ela")], odl=3, ticks=25)
sprawdz("4g nasza postać obok (nick z profil.json): nic", not sc.ctrl and sc.b.stoj_obcy_ep is None)
sc = scenariusz("pietro", [gracz(1, 0, z=6)], odl=3, ticks=25)
sprawdz("4h obcy na innym piętrze: nic", not sc.ctrl and sc.b.stoj_obcy_ep is None)
sc = scenariusz("bez_stoj", [gracz(1, 0)], odl=3, ticks=25, stoj_wl=False)
sprawdz("4i poza STÓJ (brak flagi) nic się nie zmienia: brak Ctrl+L i epizodu", not sc.ctrl and sc.b.stoj_obcy_ep is None and not (sc.k / "STOP_RECZNY").exists())

# pełny przebieg: obcy -> Ctrl+L x2 -> ekran logowania -> koniec
sc = Scena("pelny", odl=3)
sc.b.stoj_obcy_ekran = lambda: "enter_game" if len(sc.ctrl) >= 2 else "gra"
sc.tiki(2)
uh0 = sc.uh
sc.s.stwory = [gracz(2, 1, "Obcy")]
nzw = len(CAVELOG)
koniec = False
for _ in range(80):
    if not sc.b.tick():
        koniec = True
        break
sprawdz("5a tick() kończy się (bot kończy proces) po wylogowaniu", koniec and sc.b.wylogowany is True)
sprawdz("5b Ctrl+L dokładnie 2 razy, drugi >= 2 s po pierwszym", len(sc.ctrl) == 2 and sc.ctrl[1] - sc.ctrl[0] >= 2.0, sc.ctrl)
sprawdz("5c STOP i STOP_RECZNY w katalogu stanu (nadzorca/relog pomijają postać)", (sc.k / "STOP").exists() and (sc.k / "STOP_RECZNY").exists())
sprawdz("5d NIE ma wylogowany.json (kolejka relogów)", not (sc.k / "wylogowany.json").exists())
zn = json.loads((sc.k / stoj_obcy.ZNACZNIK).read_text()) if (sc.k / stoj_obcy.ZNACZNIK).exists() else {}
sprawdz("5e znacznik diagnostyczny: obcy, odległość, nick", zn.get("obcy") == "Obcy" and zn.get("odleglosc") == 2 and zn.get("nick") == "Ja", zn)
sprawdz("5f pomocnik zamykający sesję uruchomiony raz", len(sc.zamkn) == 1, sc.zamkn)
sprawdz("5g powiadomienie: jedno, kto przyszedł + wylogowana, max 3 linie", len(sc.powiad) == 1 and "Obcy" in sc.powiad[0][1]
        and "ylogowan" in (sc.powiad[0][0] + sc.powiad[0][1]) and (sc.powiad[0][0] + "\n" + sc.powiad[0][1]).count("\n") + 1 <= 3, sc.powiad)
sprawdz("5h od wykrycia do końca zero wywołań robienia run (UH)", sc.uh_w_epizodzie == 0, (uh0, sc.uh, sc.uh_w_epizodzie))
sprawdz("5i log: wykrycie i WYLOGOWANY", any("STÓJ obcy: gracz Obcy" in l for l in CAVELOG[nzw:]) and any("WYLOGOWANY" in l for l in CAVELOG[nzw:]))
sprawdz("5j kolejny tick po końcu: False, bez nowych klawiszy", sc.b.tick() is False and len(sc.ctrl) == 2)

# walka: ponawianie i poddanie się
sc = Scena("walka", odl=3)
sc.tiki(2)
sc.s.stwory = [gracz(2, 0), mob(POLE[0] + 1, POLE[1], 51)]
sc.tiki(40)
sprawdz("6a potwór obok: bot nie naciska Ctrl+L (bramka spokoju), epizod trwa", not sc.ctrl and sc.b.stoj_obcy_ep is not None and not (sc.k / "STOP_RECZNY").exists(),
        (len(sc.ctrl), sc.b.stoj_obcy_ep))
sprawdz("6b w tym czasie bot się broni (atak na potwora, nie na gracza)", len(sc.s.ataki) >= 1 and all(a[0] == 51 for a in sc.s.ataki), sc.s.ataki[:3])
uh_w_walce = sc.uh
sc.s.stwory = [gracz(2, 0)]                                  # potwór zabity -> spokój -> ponowienie
sc.tiki(15)
sprawdz("6c po walce wylogowanie ponowione (Ctrl+L)", len(sc.ctrl) >= 1, len(sc.ctrl))
sprawdz("6d w walce i po niej, póki trwa epizod, UH (runy) nie startuje", sc.uh_w_epizodzie == 0, (uh_w_walce, sc.uh, sc.uh_w_epizodzie))

sc = Scena("limit", odl=3)
sc.tiki(2)
sc.s.stwory = [gracz(2, 0), mob(POLE[0] + 1, POLE[1], 51)]
t0 = sc.s.t
n = 0
while sc.b.tick() and sc.s.t - t0 < 330 and n < 3000:
    n += 1
    if sc.b.stoj_obcy_ep is None and sc.s.t - t0 > 301:
        break
sprawdz("6e potwór przez > 300 s: poddanie się, bez Ctrl+L, bez STOP_RECZNY, bot stoi dalej", not sc.ctrl and sc.b.stoj_obcy_ep is None
        and not (sc.k / "STOP_RECZNY").exists() and sc.b.wylogowany is False and any("limit" in l for l in CAVELOG), sc.s.t - t0)
sprawdz("6f po poddaniu się powiadomienie (nie udało się wylogować) i cisza 60 s", len(sc.powiad) == 1 and sc.b.stoj_obcy_cisza_do > sc.s.t, sc.powiad)

# ---------- 7. zapisz_koniec, pomocnik, pokrętło ----------
d = TMP / "koniec"; d.mkdir()
zk = stoj_obcy.zapisz_koniec(d, "Obcy", 2, "Wydra", POLE, teraz=1000.0)
sprawdz("7a zapisz_koniec: STOP, STOP_RECZNY, znacznik", (d / "STOP").exists() and (d / "STOP_RECZNY").exists() and (d / stoj_obcy.ZNACZNIK).exists() and "blad" not in zk, zk)
zk = stoj_obcy.zapisz_koniec(TMP / "nie_ma_takiego_katalogu", "Obcy", 2, "Wydra", POLE)
sprawdz("7b zapisz_koniec: błąd zapisu nie rzuca, jest w znaczniku `blad`", "blad" in zk, zk)

wywolania = []
kod = stoj_obcy.zamknij(4242, zyje=lambda pid: False, uruchom=lambda cmd: wywolania.append(cmd) or 0, spij=lambda s: None)
cmd = wywolania[0] if wywolania else []
sprawdz("7c pomocnik wywołuje wyłącznie `logowanie.py wyloguj --reczny-ok` (nigdy zaloguj)", kod == 0 and len(cmd) == 5 and cmd[2].endswith("/logowanie.py")
        and cmd[3:] == ["wyloguj", "--reczny-ok"], cmd)
sprawdz("7c' w poleceniu nie ma `zaloguj`", wywolania and not any("zaloguj" in str(x).replace("wyloguj", "") for x in cmd), cmd)
zegar = [0.0]
stan_pid = [True]
def spij_(s):
    zegar[0] += s
    if zegar[0] >= 3:
        stan_pid[0] = False
wywolania.clear()
stoj_obcy.zamknij(4242, zyje=lambda pid: stan_pid[0], uruchom=lambda cmd: wywolania.append(cmd) or 0, spij=spij_, zegar=lambda: zegar[0])
sprawdz("7d pomocnik czeka na koniec procesu bota, potem zamyka (nie wcześniej)", wywolania and zegar[0] >= 3, zegar[0])
sprawdz("7e main: złe argumenty = kod 2", stoj_obcy.main([]) == 2 and stoj_obcy.main(["zamknij", "x"]) == 2)

sprawdz("7f pokrętło w ZAKRESY (0-14) i KIERUNEK nie_wyzej (analityk nie włączy)", pokretla.ZAKRESY.get("STOJ_GRACZ_WYLOGUJ_ODL") == (0, 14)
        and pokretla.KIERUNEK.get("STOJ_GRACZ_WYLOGUJ_ODL") == "nie_wyzej")
poprawne, bledy = pokretla.waliduj({"STOJ_GRACZ_WYLOGUJ_ODL": 3})
sprawdz("7g okno_api ustaw: 3 poprawne", poprawne == {"STOJ_GRACZ_WYLOGUJ_ODL": 3} and not bledy, (poprawne, bledy))
poprawne, bledy = pokretla.waliduj({"STOJ_GRACZ_WYLOGUJ_ODL": 15})
sprawdz("7h 15 poza zakresem odrzucone", not poprawne and bledy, bledy)
poprawne, bledy = pokretla.waliduj({"STOJ_GRACZ_WYLOGUJ_ODL": 3}, {"STOJ_GRACZ_WYLOGUJ_ODL": 0})
sprawdz("7i analityk (z domyślnymi): podniesienie z 0 odrzucone", not poprawne and bledy, (poprawne, bledy))
sprawdz("7j domyślnie 0 w cavebot.py (wyłączone globalnie)", getattr(cavebot, "STOJ_GRACZ_WYLOGUJ_ODL", None) is not None)

# nicki_naszych na prawdziwej funkcji (z podmienionym katalogiem)
import importlib
importlib.reload(stoj_obcy)
kat_i = TMP / "instancje"
for nazwa_i, nick_i in (("wydra", "Wydra"), ("ela", "Ela"), ("pusty", ""), ("zepsuty", None)):
    (kat_i / nazwa_i).mkdir(parents=True)
    if nick_i is None:
        (kat_i / nazwa_i / "profil.json").write_text("{zepsuty")
    else:
        (kat_i / nazwa_i / "profil.json").write_text(json.dumps({"postac": nick_i}))
sprawdz("7k nicki_naszych: z profil.json, pusty i zepsuty pomijane", stoj_obcy.nicki_naszych(kat_i) == {"wydra", "ela"}, stoj_obcy.nicki_naszych(kat_i))

print(f"{sum(ok)}/{len(ok)}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(ok) else 1)
