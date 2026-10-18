#!/usr/bin/env python3
"""15.10 SPEC_obrona_pk_1015 pkt 2-4: czaszka obcego gracza ze zrzutu (Haiku, atrapa modelu), "czaszka: nieznana"
w kontekście modelu, zakaz zgadywania w prompcie, czary innych graczy (exura...) to nie wiadomości do bota.
Zero prawdziwych wywołań modelu, zero inputu do gry."""
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

import cavebot  # noqa: E402
import czaszka  # noqa: E402
import mozg  # noqa: E402

wyniki = []
tmp = Path(tempfile.mkdtemp())


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


class Zegar:
    def __init__(s, t=1000.0):
        s.t = t

    def __call__(s):
        return s.t


class Haiku:
    """Atrapa modelu: zwraca kolejne odpowiedzi, liczy wywołania, zapamiętuje obraz i system."""
    def __init__(s, *odp):
        s.odp, s.wywolania, s.obrazy, s.systemy = list(odp), 0, [], []

    def __call__(s, prompt, system=None, obraz=None):
        s.wywolania += 1
        s.systemy.append(system)
        s.obrazy.append(obraz and Path(obraz).exists())    # plik musi istnieć w chwili wywołania
        o = s.odp.pop(0) if len(s.odp) > 1 else s.odp[0]
        if isinstance(o, Exception):
            raise o
        return o, {"total_cost_usd": 0.001}


def czytnik(model, zeg, **kw):
    logi = []
    r = czaszka.CzytnikCzaszki(model, zrzut=lambda: Image.new("RGB", (1536, 960)), katalog=tmp / "k",
                               log=logi.append, zegar=zeg, wytnij=lambda o, dx, dy: Image.new("RGB", (30, 20)), **kw)
    r.logi = logi
    return r


# --- A: odczyt, kesz, limit, pokrętła ---
czaszka.wyczysc()
z = Zegar(); h = Haiku("white")
r = czytnik(h, z)
sprawdz("A1 odczyt: biala trafia do magazynu", r.odczytaj("Krzyssxd", 1, 0) == "biala"
        and czaszka.czaszka_gracza("krzyssxd", z) == "biala" and czaszka.czaszka_grozna("Krzyssxd", z))
sprawdz("A1b obraz poszedł do modelu jako istniejący plik, system po angielsku z 'white'", h.obrazy == [True]
        and "WHITE skull" in h.systemy[0])
sprawdz("A1c plik tymczasowy sprzątnięty", not list((tmp / "k").glob("czaszka-*.png")))
r.odczytaj("Krzyssxd", 1, 0); r.odczytaj("KRZYSSXD", 1, 0)
sprawdz("A2 kesz per nick (także inna wielkość liter): 1 wywołanie", h.wywolania == 1, h.wywolania)
z.t += czaszka.TTL_CZASZKA_S + 1
sprawdz("A3 po TTL kesz wygasa: None w magazynie, ponowny odczyt", czaszka.czaszka_gracza("Krzyssxd", z) is None
        and r.odczytaj("Krzyssxd", 1, 0) == "biala" and h.wywolania == 2)

czaszka.wyczysc(); z = Zegar(); h = Haiku("none", "red", "unreadable", "I think maybe a white skull on the left", "RED.")
r = czytnik(h, z)
sprawdz("A4 'none' -> brak (odczytano, bez czaszki)", r.odczytaj("A", 0, 1) == "brak" and czaszka.czaszka_gracza("A", z) == "brak"
        and not czaszka.czaszka_grozna("A", z))
sprawdz("A5 red -> czerwona, groźna", r.odczytaj("B", 0, 1) == "czerwona" and czaszka.czaszka_grozna("B", z))
sprawdz("A6 unreadable -> magazyn zwraca None (brak odczytu), model dostaje 'nieznana'",
        r.odczytaj("C", 0, 1) == "nieczytelne" and czaszka.czaszka_gracza("C", z) is None
        and czaszka.dla_modelu("C", z) == "nieznana")
sprawdz("A7 rozwlekła odpowiedź = nieczytelne (nie zgadujemy)", r.odczytaj("D", 0, 1) == "nieczytelne"
        and czaszka.czaszka_gracza("D", z) is None)
sprawdz("A8 'RED.' z kropką = czerwona", r.odczytaj("E", 0, 1) == "czerwona")
z.t += czaszka.TTL_NIECZYTELNE_S + 1
n = h.wywolania
sprawdz("A9 nieczytelne ponawiane po krótkim TTL", r.odczytaj("C", 0, 1) is not None and h.wywolania == n + 1)

czaszka.wyczysc(); z = Zegar(); h = Haiku("none")
r = czytnik(h, z, limit_h=3)
wyn = [r.odczytaj(f"Gracz{i}", 0, 1) for i in range(5)]
sprawdz("B1 limit 3/h: trzy odczyty, reszta None, model wołany 3 razy", wyn == ["brak"] * 3 + [None, None]
        and h.wywolania == 3, (wyn, h.wywolania))
sprawdz("B2 limit zalogowany raz", sum("limit 3 odczytów" in l for l in r.logi) == 1, r.logi)
sprawdz("B3 przy limicie czaszka 'nieznana', nie 'brak'", czaszka.dla_modelu("Gracz4", z) == "nieznana")
z.t += 3601
sprawdz("B4 po godzinie limit się odnawia", r.odczytaj("Gracz4", 0, 1) == "brak" and h.wywolania == 4)

czaszka.wyczysc(); h = Haiku("white"); z = Zegar()
r = czytnik(h, z, wlaczony=False)
sprawdz("B5 CZASZKA_ODCZYT=0: bez wywołań i bez wpisu", r.odczytaj("X", 0, 1) is None and h.wywolania == 0
        and r.zlec([("X", 0, 1)]) is None and czaszka.czaszka_gracza("X", z) is None)
os.environ["CZASZKA_ODCZYT"], os.environ["CZASZKA_LIMIT_H"] = "1", "1"
r = czytnik(h, z)
r.odczytaj("P", 0, 1); r.odczytaj("Q", 0, 1)
sprawdz("B6 pokrętła z env: CZASZKA_LIMIT_H=1 -> jedno wywołanie", h.wywolania == 1 and r.limit_h == 1 and r.wlaczony)
del os.environ["CZASZKA_ODCZYT"], os.environ["CZASZKA_LIMIT_H"]
sprawdz("B7 domyślne: odczyt włączony, limit 20/h", czytnik(h, z).wlaczony and czytnik(h, z).limit_h == 20)

czaszka.wyczysc(); z = Zegar(); h = Haiku(RuntimeError("timeout"))
r = czytnik(h, z)
sprawdz("B8 błąd modelu: None, nic w magazynie, próba policzona do limitu",
        r.odczytaj("Y", 0, 1) is None and czaszka.czaszka_gracza("Y", z) is None and len(r.wywolania) == 1
        and any("nie powiódł" in l for l in r.logi))

# zlec: wątek, tylko bez świeżego wpisu, najbliżsi
czaszka.wyczysc(); z = Zegar(); h = Haiku("none")
r = czytnik(h, z)
w = r.zlec([("N1", 1, 0), ("N2", 2, 0), ("N3", 3, 0)])
w.join(5)
sprawdz("B9 zlec: wątek czyta najwyżej MAKS_NA_RAZ graczy", h.wywolania == czaszka.MAKS_NA_RAZ, h.wywolania)
sprawdz("B10 zlec: po odczycie nic nowego do roboty dla tych samych", r.zlec([("N1", 1, 0), ("N2", 2, 0)]) is None)

# prawdziwy wycinek (ekran.py): rozmiar i granice
obraz = Image.new("RGB", (1536, 960), (10, 10, 10))
wyc = czaszka.wytnij_nick(obraz, 1, 0, prostokat=(127, 38, 1227, 845))
sprawdz("B11 wytnij_nick: wycinek 5x2 pola, powiększony", wyc.size[0] > 300 and wyc.size[1] > 100, wyc.size)
sprawdz("B12 wytnij_nick przy krawędzi mapy nie wychodzi poza obraz",
        czaszka.wytnij_nick(obraz, -7, -5, prostokat=(0, 0, 1100, 807)).size[0] > 0)

# --- C: cavebot czyta magazyn (hak minimalny) ---
czaszka.wyczysc()
bob = {"nazwa": "Bob", "gracz": True}
sprawdz("C1 gracz_grozny: bez odczytu nie groźny", not cavebot.Cavebot.gracz_grozny(bob))
czaszka.ustaw("Bob", "brak", 300)
sprawdz("C2 gracz_grozny: odczyt 'brak' nie groźny", not cavebot.Cavebot.gracz_grozny(bob))
czaszka.ustaw("Bob", "czerwona", 300)
sprawdz("C3 gracz_grozny: czerwona = groźny", cavebot.Cavebot.gracz_grozny(bob))
sprawdz("C4 GM nadal groźny po nicku", cavebot.Cavebot.gracz_grozny({"nazwa": "GM Tester", "gracz": True}))

# --- D: kontekst modelu i prompt ---
class Gniazdo:
    def __init__(s):
        s.stwory = [{"id": 2, "nazwa": "Bob", "gracz": True, "x": 32021, "y": 32150, "z": 8, "hp": 100}]
        s.czat = []

    def __call__(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 150, "max_hp": 165, "cap": 240, "exp": 1, "level": 4, "procent": 3, "mana": 1, "max_mana": 1}}
        if z["cmd"] == "pozycja":
            return {"pozycja": {"x": 32020, "y": 32150, "z": 8}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": 32020, "y": 32150, "z": 8, "hp": 100}] + s.stwory}
        if z["cmd"] == "wiadomosci":
            lista = [dict(w, nr=i + 1) for i, w in enumerate(s.czat)]
            return {"wiadomosci": lista, "znacznik": len(lista), "epoka": "e"}
        raise RuntimeError("?")


class ModelDecyzji:
    def __init__(s):
        s.prompty = []

    def __call__(s, prompt, **kw):
        s.prompty.append(prompt)
        return '{"mysl":"ok","akcje":[{"typ":"kontynuuj"}]}', {}


def mozg_doradca(model, gniazdo, **kw):
    logi = []
    m = mozg.Mozg("doradca", zapytaj=gniazdo, nazwa="Ja", model=model, pamiec=mozg.Pamiec(tmp / "p.json"),
                  log=lambda *a: logi.append(" ".join(map(str, a))), zegar=Zegar(), trasy=lambda: ["t"],
                  losuj=lambda a, b: a, **kw)
    m.logi = logi
    return m


czaszka.wyczysc()
g = Gniazdo(); md = ModelDecyzji(); m = mozg_doradca(md, g)
stan = m.zbuduj_stan()
sprawdz("D1 stan: gracz bez odczytu ma czaszka 'nieznana' (nie brak, nie pusty)",
        stan["gracze_w_widoku"][0].get("czaszka") == "nieznana", stan["gracze_w_widoku"])
sprawdz("D1b w JSON-ie promptu jest 'czaszka':'nieznana'", '"czaszka":"nieznana"' in m.prompt(stan))
m.zdarzenia.gracze({"Bob"})
zd = m.zdarzenia.pobierz()
p = m.prompt_zdarzenia(stan, zd)
sprawdz("D2 zdarzenie obcy_gracz niesie czaszki: nieznana", '"czaszki": {"Bob": "nieznana"}' in p, p[:300])
czaszka.ustaw("Bob", "biala", 600)
stan = m.zbuduj_stan()
sprawdz("D3 po odczycie stan niesie 'biala'", stan["gracze_w_widoku"][0]["czaszka"] == "biala")
czaszka.ustaw("Bob", "brak", 600)
sprawdz("D3b 'brak' to odczytane 'brak', nie 'nieznana'", m.zbuduj_stan()["gracze_w_widoku"][0]["czaszka"] == "brak")
sprawdz("D4 prompt zakazuje pisać 'bez czaszki' bez odczytu", "NIE WOLNO" in mozg.SYSTEM and "nieznana" in mozg.SYSTEM
        and 'tylko przy "brak"' in mozg.SYSTEM)
sprawdz("D5 stary założenie 'bez czaszki' wycięte z reguł graczy: 'Zwykły obcy gracz (bez czaszki' nie istnieje",
        "Zwykły obcy gracz w widoku (bez czaszki" not in mozg.SYSTEM)

# --- E: hak mózgu: zlecenie odczytu, czekanie ---
class FalszywyCzytnik:
    def __init__(s):
        s.zlecenia, s.czekano = [], []

    def zlec(s, g):
        s.zlecenia.append(list(g))

    def czekaj(s, sek):
        s.czekano.append(sek)


czaszka.wyczysc()
fc = FalszywyCzytnik()
m = mozg_doradca(ModelDecyzji(), Gniazdo(), czytnik_czaszki=fc)
odczyt = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 7},
          {"id": 2, "nazwa": "Far", "gracz": True, "x": 104, "y": 100, "z": 7},
          {"id": 3, "nazwa": "Near", "gracz": True, "x": 101, "y": 101, "z": 7}]
m.cb = types.SimpleNamespace(odczyt_stworow=(1.0, odczyt),
                             inni_gracze=lambda l, poz: [s for s in l if s["nazwa"] != "Ja"])
m.czaszki_ze_stworow()   # 16.10: zlecanie przeniesione z czas_na_pytanie (działa też w trybie skrypt)
sprawdz("E1 nowi obcy w widoku -> zlecenie odczytu, najbliższy pierwszy, z dx,dy",
        fc.zlecenia == [[("Near", 1, 1), ("Far", 4, 0)]], fc.zlecenia)
m.zdarzenia.gracze({"Near"})
m.cb = None   # pomysl() w doradcy; czekanie na odczyt przed pytaniem o obcego gracza
m.pomysl(m.zdarzenia.pobierz())
sprawdz("E2 pytanie o obcego gracza czeka na odczyt czaszki", fc.czekano == [mozg.CZASZKA_CZEKAJ_S], fc.czekano)
sprawdz("E3 Mozg z atrapą modelu bez czytnika: odczyt wyłączony (brak przypadkowych wywołań)",
        mozg_doradca(ModelDecyzji(), Gniazdo()).czytnik_czaszki is None)

# --- F: czary innych graczy to nie wiadomości do bota ---
def czat_bez_odpowiedzi(tekst, autor="Loveliy", na_ekranie=("Loveliy",), kanal="Default"):
    wall = [1_700_000_000.0]
    zeg = Zegar()
    surowe = []
    c = mozg.Czat(lambda zad: {"wiadomosci": list(surowe), "znacznik": len(surowe), "epoka": 1}, "Ja", zeg,
                  zegar_scienny=lambda: wall[0], log=lambda t: None)
    c.na_ekranie = na_ekranie
    c.odswiez()                                   # punkt odniesienia
    surowe.append({"nadawca": autor, "tekst": tekst, "kanal": kanal, "czas": "", "nr": 1})
    nowe = c.odswiez()
    return c, nowe


for czar in ("exura", "exura gran", "exura vita", "utani hur", "utani gran hur", "utevo lux", "utevo gran lux",
             "adura vita", "adori gran", "adori vita vis", "exori", "exevo pan", "utamo vita", "Exura", "exeta res"):
    c, nowe = czat_bez_odpowiedzi(czar)
    sprawdz(f"F1 czar {czar!r} od jedynego gracza w widoku: nie zaczepka, bez celu, bez zdarzenia",
            nowe == 0 and not c.cele and not c.do_nas and not c.nowi_autorzy and c.nowe_obce == 0
            and not c.mozna_wyslac()[0] and c.cel_odpowiedzi() is None, (nowe, c.cele, c.nowi_autorzy))
c, nowe = czat_bez_odpowiedzi("exura", kanal="Loveliy")     # priv z samym czarem
sprawdz("F2 czar na priv też nie jest wiadomością do bota", nowe == 0 and not c.cele)
c, nowe = czat_bez_odpowiedzi("exura")
sprawdz("F3 czar zostaje w kontekście modelu, oznaczony czar:true i nowa:false",
        c.dla_modelu()[-1].get("czar") is True and not c.dla_modelu()[-1].get("nowa"), c.dla_modelu())
for tekst in ("hi", "hej", "yo what's up?"):
    c, nowe = czat_bez_odpowiedzi(tekst)
    sprawdz(f"F4 {tekst!r} od jedynego gracza nadal zaczepka do bota (odpowiedź możliwa)",
            nowe == 1 and "Loveliy" in c.cele and c.mozna_wyslac()[0] and c.cel_odpowiedzi() == "Loveliy", (nowe, c.cele))
sprawdz("F5 do_nas: czar nigdy nie do nas, nawet z nickiem i na priv",
        not mozg.do_nas("Bob", "exura", "Default", "Ja", na_ekranie=("Bob",))
        and not mozg.do_nas("Bob", "utevo lux", "Bob", "Ja") and mozg.do_nas("Bob", "hi", "Bob", "Ja"))
sprawdz("F6 zwykłe zdania zaczynające się podobnie nie są czarem", not mozg.CZAR_TEKST.match("excuse me bro")
        and not mozg.CZAR_TEKST.match("utility?") and not mozg.CZAR_TEKST.match("adore this spot"))
c, nowe = czat_bez_odpowiedzi("exura", autor="GM Test", na_ekranie=("GM Test",))
sprawdz("F7 GM piszący 'exura' nadal liczy się jako wiadomość (alarm po nicku)", nowe == 1 and c.alarmy, c.alarmy)
sprawdz("F8 prompt: wpisy z czar:true to nie wiadomości", '"czar": true' in mozg.SYSTEM)

ok = sum(wyniki)
print(f"\n{ok}/{len(wyniki)}")
sys.exit(0 if ok == len(wyniki) else 1)
